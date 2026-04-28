import json
import sys

res = {
    "executable": sys.executable,
    "django_import_ok": False,
    "torch_import_ok": False,
    "torch_version": None,
    "torch_cuda_version": None,
    "cuda_available": False,
    "cuda_device_count": 0
}

try:
    import django
    res["django_import_ok"] = True
except ImportError:
    pass

try:
    import torch
    res["torch_import_ok"] = True
    res["torch_version"] = torch.__version__
    res["torch_cuda_version"] = torch.version.cuda
    res["cuda_available"] = torch.cuda.is_available()
    res["cuda_device_count"] = torch.cuda.device_count()
except ImportError:
    pass

print(json.dumps(res, indent=2))
