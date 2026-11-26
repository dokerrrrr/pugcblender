"""Measure time and project replacements for one-by-one and batched updates."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from pugc_toolkit import batch_edit
from pugc_toolkit.ugc_project import new_project, transform
from pugc_toolkit.ugc_storage import json_bytes


def measure(project, request, batches):
    start = perf_counter()
    with patch.object(batch_edit, "atomic_write", wraps=batch_edit.atomic_write) as write:
        for operations in batches:
            digest = sha256(project.read_bytes()).hexdigest()
            request.write_bytes(json_bytes({"schema": 1, "base_sha256": digest, "operations": operations}))
            result = batch_edit.edit(project, request)
            if result["exit_code"]:
                raise ValueError(result["diagnostics"])
    return {"elapsed_s": round(perf_counter() - start, 3), "project_writes": write.call_count}


if __name__ == "__main__":
    scene = new_project("3,000 instances")
    scene["instances"] = [{"id": f"post-{index}", "objectId": 12005, "assembly": "Before", "zone": "near",
                           "transform": transform((index, 0, 0))}
                          for index in range(3000)]
    operations = [{"op": "update", "id": f"post-{index}", "fields": {"assembly": "After"}} for index in range(100)]
    with TemporaryDirectory() as directory:
        one, bulk, request = (Path(directory) / name for name in ("one.json", "bulk.json", "request.json"))
        one.write_bytes(json_bytes(scene))
        bulk.write_bytes(one.read_bytes())
        serial = measure(one, request, ([operation] for operation in operations))
        batched = measure(bulk, request, [operations])
        if one.read_bytes() != bulk.read_bytes():
            raise ValueError("Serial and batched edits produced different results")
        print(json.dumps({"instances": 3000, "operations": 100, "serial": serial, "batch": batched}, indent=2))
