"""Generate a single-node K3s pilot manifest from the Compose service definition.

No credentials are emitted. Create hse-secrets separately before deployment.
Use --registry registry.local/hse --tag 0.1.0 to choose built application images.
"""

import argparse
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def manifest(registry, tag):
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    ns = "hse-video"
    yield {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": ns}}
    for name, size in [
        ("postgres", "10Gi"),
        ("redis", "2Gi"),
        ("evidence", "20Gi"),
        ("minio", "20Gi"),
        ("models", "10Gi"),
    ]:
        yield {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": name, "namespace": ns},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": size}},
            },
        }
    nginx = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    yield {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "hse-nginx", "namespace": ns},
        "data": {"default.conf": nginx},
    }
    environment = {
        "backend": {
            "DATABASE_URL": ("secret", "DATABASE_URL"),
            "REDIS_URL": "redis://redis:6379/0",
            "DEMO_MODE": "true",
            "SERVICE_TOKEN": ("secret", "SERVICE_TOKEN"),
            "OPERATOR_TOKEN": ("secret", "OPERATOR_TOKEN"),
            "INFERENCE_URL": "http://inference:8001",
            "MEDIA_DIR": "/data/snapshots",
            "S3_ENDPOINT": "http://minio:9000",
            "S3_ACCESS_KEY": ("secret", "S3_ACCESS_KEY"),
            "S3_SECRET_KEY": ("secret", "S3_SECRET_KEY"),
            "S3_BUCKET": "hse-evidence",
        },
        "inference": {
            "SERVICE_TOKEN": ("secret", "SERVICE_TOKEN"),
            "ONNX_PROVIDER": "CPUExecutionProvider",
            "DETECTOR_MODEL": "/models/person.onnx",
            "PPE_MODEL": "/models/ppe.onnx",
            "POSE_MODEL": "/models/pose.onnx",
            "BEHAVIOR_MODEL": "/models/behavior.onnx",
        },
        "ingestion": {
            "SERVICE_TOKEN": ("secret", "SERVICE_TOKEN"),
            "BACKEND_URL": "http://backend:8000",
            "INFERENCE_URL": "http://inference:8001",
            "INFERENCE_FPS": "8",
        },
        "postgres": {
            "POSTGRES_DB": "hse",
            "POSTGRES_USER": "hse",
            "POSTGRES_PASSWORD": ("secret", "POSTGRES_PASSWORD"),
            "PGDATA": "/var/lib/postgresql/data/pgdata",
        },
        "minio": {
            "MINIO_ROOT_USER": ("secret", "S3_ACCESS_KEY"),
            "MINIO_ROOT_PASSWORD": ("secret", "S3_SECRET_KEY"),
        },
    }
    ports = {
        "frontend": 80,
        "backend": 8000,
        "inference": 8001,
        "postgres": 5432,
        "redis": 6379,
        "minio": 9000,
    }
    mounts = {
        "backend": [("evidence", "/data/snapshots")],
        "inference": [("models", "/models")],
        "postgres": [("postgres", "/var/lib/postgresql/data")],
        "redis": [("redis", "/data")],
        "minio": [("minio", "/data")],
    }
    for name, source in compose["services"].items():
        container = {
            "name": name,
            "image": (
                f"{registry}/{name}:{tag}" if "build" in source else source["image"]
            ),
            "imagePullPolicy": "IfNotPresent",
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"memory": "8Gi" if name == "inference" else "2Gi"},
            },
        }
        if name in environment:
            container["env"] = [
                (
                    {
                        "name": k,
                        "valueFrom": {
                            "secretKeyRef": {"name": "hse-secrets", "key": v[1]}
                        },
                    }
                    if isinstance(v, tuple)
                    else {"name": k, "value": v}
                )
                for k, v in environment[name].items()
            ]
        if "command" in source:
            if name == "minio":
                container["args"] = ["server", "/data"]
            else:
                container["command"] = source["command"]
        pod = {"containers": [container]}
        if name in mounts:
            container["volumeMounts"] = [
                {"name": volume, "mountPath": path, "readOnly": name == "inference"}
                for volume, path in mounts[name]
            ]
            pod["volumes"] = [
                {"name": volume, "persistentVolumeClaim": {"claimName": volume}}
                for volume, _ in mounts[name]
            ]
        if name in ("backend", "inference", "ingestion"):
            pod["securityContext"] = {
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "fsGroup": 10001,
            }
        if name == "frontend":
            container["volumeMounts"] = [
                {
                    "name": "nginx",
                    "mountPath": "/etc/nginx/conf.d/default.conf",
                    "subPath": "default.conf",
                }
            ]
            pod["volumes"] = [{"name": "nginx", "configMap": {"name": "hse-nginx"}}]
        if name in ("backend", "inference", "frontend"):
            probe = {
                "httpGet": {
                    "path": (
                        "/api/health"
                        if name == "backend"
                        else "/health" if name == "inference" else "/"
                    ),
                    "port": ports[name],
                },
                "periodSeconds": 10,
            }
            container["readinessProbe"] = probe
            container["livenessProbe"] = {**probe, "initialDelaySeconds": 30}
        if name in ports:
            container["ports"] = [{"containerPort": ports[name]}]
        yield {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": ns},
            "spec": {
                "replicas": 1,
                "strategy": {"type": "Recreate"},
                "selector": {"matchLabels": {"app": name}},
                "template": {"metadata": {"labels": {"app": name}}, "spec": pod},
            },
        }
        if name in ports:
            yield {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name, "namespace": ns},
                "spec": {
                    "selector": {"app": name},
                    "ports": [{"port": ports[name], "targetPort": ports[name]}],
                },
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="hse")
    parser.add_argument("--tag", default="0.1.0")
    parser.add_argument("--output", default=str(ROOT / "deploy/k8s.yaml"))
    args = parser.parse_args()
    Path(args.output).write_text(
        yaml.safe_dump_all(
            list(manifest(args.registry, args.tag)), allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    print(f"Manifest written to {args.output}")
