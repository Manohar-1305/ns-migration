from kubernetes import client, config, watch
import os
from kubernetes.client.exceptions import ApiException

# Load Kubeconfig (inside cluster or local)
if "KUBERNETES_SERVICE_HOST" in os.environ:
    config.load_incluster_config()
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
        if e.status == 409:
            print(f"⚠️ Namespace {target_ns} already exists, skipping creation.")
        else:
            raise

    # Migrate Deployments
    deployments = apps_api.list_namespaced_deployment(source_ns).items
    for deploy in deployments:
        deploy.metadata.namespace = target_ns
        deploy.metadata.resource_version = None
        try:
            apps_api.create_namespaced_deployment(target_ns, deploy)
            print(f"✅ Deployment {deploy.metadata.name} migrated successfully.")
            apps_api.delete_namespaced_deployment(deploy.metadata.name, source_ns)
        except ApiException as e:
            print(f"❌ Error migrating Deployment {deploy.metadata.name}: {e}")

    # Migrate StatefulSets
    statefulsets = apps_api.list_namespaced_stateful_set(source_ns).items
    for sts in statefulsets:
        sts.metadata.namespace = target_ns
        sts.metadata.resource_version = None
        try:
            apps_api.create_namespaced_stateful_set(target_ns, sts)
            print(f"✅ StatefulSet {sts.metadata.name} migrated successfully.")
            apps_api.delete_namespaced_stateful_set(sts.metadata.name, source_ns)
        except ApiException as e:
            print(f"❌ Error migrating StatefulSet {sts.metadata.name}: {e}")

    # Migrate PVCs (Skip Local PVCs)
    pvcs = core_api.list_namespaced_persistent_volume_claim(source_ns).items
    for pvc in pvcs:
        pvc_name = pvc.metadata.name
        try:
            # Get PVC details
            pvc_info = core_api.read_namespaced_persistent_volume_claim(pvc_name, source_ns)
            storage_class = pvc_info.spec.storage_class_name

            # Check if PVC is using local storage
            if storage_class is None or "local" in storage_class.lower():
                print(f"⏭️ Skipping local PVC {pvc_name} (hostPath/local storage).")
                continue  # Skip migration

            # Migrate non-local PVC
            pvc.metadata.namespace = target_ns
            pvc.metadata.resource_version = None
            core_api.create_namespaced_persistent_volume_claim(target_ns, pvc)
            print(f"✅ PVC {pvc_name} migrated successfully.")
            core_api.delete_namespaced_persistent_volume_claim(pvc_name, source_ns)
        except ApiException as e:
            print(f"❌ Error migrating PVC {pvc_name}: {e}")

    # Migrate ConfigMaps
    configmaps = core_api.list_namespaced_config_map(source_ns).items
    for cm in configmaps:
        cm.metadata.namespace = target_ns
        cm.metadata.resource_version = None
        try:
            core_api.create_namespaced_config_map(target_ns, cm)
            print(f"✅ ConfigMap {cm.metadata.name} migrated successfully.")
            core_api.delete_namespaced_config_map(cm.metadata.name, source_ns)
        except ApiException as e:
            print(f"❌ Error migrating ConfigMap {cm.metadata.name}: {e}")

    # Migrate Secrets
    secrets = core_api.list_namespaced_secret(source_ns).items
    for secret in secrets:
        secret.metadata.namespace = target_ns
        secret.metadata.resource_version = None
        try:
            core_api.create_namespaced_secret(target_ns, secret)
            print(f"✅ Secret {secret.metadata.name} migrated successfully.")
            core_api.delete_namespaced_secret(secret.metadata.name, source_ns)
        except ApiException as e:
            print(f"❌ Error migrating Secret {secret.metadata.name}: {e}")

    # Delete namespace if empty
    try:
        resources_left = (
            len(core_api.list_namespaced_pod(source_ns).items) +
            len(core_api.list_namespaced_config_map(source_ns).items) +
            len(core_api.list_namespaced_secret(source_ns).items) +
            len(core_api.list_namespaced_persistent_volume_claim(source_ns).items) +
            len(apps_api.list_namespaced_deployment(source_ns).items) +
            len(apps_api.list_namespaced_stateful_set(source_ns).items)
        )

        if resources_left == 0:
            core_api.delete_namespace(source_ns)
            print(f"✅ Namespace {source_ns} deleted successfully.")
        else:
            print(f"⚠️ Namespace {source_ns} still contains resources, not deleted.")
    except ApiException as e:
        print(f"❌ Error deleting namespace {source_ns}: {e}")

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
