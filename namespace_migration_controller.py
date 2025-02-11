from kubernetes import client, config, watch
import os
from kubernetes.client.exceptions import ApiException

# Automatically use in-cluster config if inside a pod, otherwise use local kubeconfig
if "KUBERNETES_SERVICE_HOST" in os.environ:
    config.load_incluster_config()  # Running inside a pod
else:
    config.load_kube_config()

api = client.CustomObjectsApi()
core_api = client.CoreV1Api()
apps_api = client.AppsV1Api()

CRD_GROUP = "example.com"
CRD_VERSION = "v1"
CRD_PLURAL = "namespacemigrations"

def migrate_namespace(source_ns, target_ns):
    print(f"🚀 Starting migration from {source_ns} to {target_ns}...")

    # Ensure target namespace exists
    try:
        core_api.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=target_ns)))
        print(f"✅ Created namespace: {target_ns}")
    except ApiException as e:
        if e.status == 409:  # Namespace already exists
            print(f"⚠️ Namespace {target_ns} already exists, skipping creation.")
        else:
            raise

    # Migrate Deployments
    deployments = apps_api.list_namespaced_deployment(source_ns).items
    for deploy in deployments:
        deploy.metadata.namespace = target_ns
        deploy.metadata.resource_version = None  # Remove old version info

        try:
            apps_api.create_namespaced_deployment(target_ns, deploy)
            print(f"✅ Deployment {deploy.metadata.name} migrated successfully.")
        except ApiException as e:
            if e.status == 409:
                print(f"⚠️ Deployment {deploy.metadata.name} already exists in {target_ns}, skipping.")
            else:
                print(f"❌ Error migrating Deployment {deploy.metadata.name}: {e}")
                raise

    # Migrate ConfigMaps
    configmaps = core_api.list_namespaced_config_map(source_ns).items
    for cm in configmaps:
        cm.metadata.namespace = target_ns
        cm.metadata.resource_version = None

        try:
            core_api.create_namespaced_config_map(target_ns, cm)
            print(f"✅ ConfigMap {cm.metadata.name} migrated successfully.")
        except ApiException as e:
            if e.status == 409:
                print(f"⚠️ ConfigMap {cm.metadata.name} already exists in {target_ns}, skipping.")
            else:
                print(f"❌ Error migrating ConfigMap {cm.metadata.name}: {e}")
                raise

    # Migrate Secrets
    secrets = core_api.list_namespaced_secret(source_ns).items
    for secret in secrets:
        secret.metadata.namespace = target_ns
        secret.metadata.resource_version = None

        try:
            core_api.create_namespaced_secret(target_ns, secret)
            print(f"✅ Secret {secret.metadata.name} migrated successfully.")
        except ApiException as e:
            if e.status == 409:
                print(f"⚠️ Secret {secret.metadata.name} already exists in {target_ns}, skipping.")
            else:
                print(f"❌ Error migrating Secret {secret.metadata.name}: {e}")
                raise

    print(f"🎉 Migration completed from {source_ns} to {target_ns}")

def watch_migrations():
    w = watch.Watch()
    print("👀 Watching for namespace migration CRDs...")
    for event in w.stream(api.list_cluster_custom_object, CRD_GROUP, CRD_VERSION, CRD_PLURAL):
        migration = event['object']
        source_ns = migration['spec']['sourceNamespace']
        target_ns = migration['spec']['targetNamespace']
        migrate_namespace(source_ns, target_ns)

if __name__ == "__main__":
    watch_migrations()
