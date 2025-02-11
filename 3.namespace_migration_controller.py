from kubernetes import client, config, watch

# Load kubeconfig from default location (~/.kube/config)
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
    except client.exceptions.ApiException:
        pass  # Namespace already exists

    # Migrate Deployments
    deployments = apps_api.list_namespaced_deployment(source_ns).items
    for deploy in deployments:
        deploy.metadata.namespace = target_ns
        deploy.metadata.resource_version = None  # Remove old version info
        apps_api.create_namespaced_deployment(target_ns, deploy)

    # Migrate Services
    services = core_api.list_namespaced_service(source_ns).items
    for svc in services:
        svc.metadata.namespace = target_ns
        svc.metadata.resource_version = None
        core_api.create_namespaced_service(target_ns, svc)

    # Migrate ConfigMaps
    configmaps = core_api.list_namespaced_config_map(source_ns).items
    for cm in configmaps:
        cm.metadata.namespace = target_ns
        cm.metadata.resource_version = None
        core_api.create_namespaced_config_map(target_ns, cm)

    print(f"✅ Migration completed from {source_ns} to {target_ns}")

def watch_migrations():
    w = watch.Watch()
    for event in w.stream(api.list_cluster_custom_object, CRD_GROUP, CRD_VERSION, CRD_PLURAL):
        migration = event['object']
        source_ns = migration['spec']['sourceNamespace']
        target_ns = migration['spec']['targetNamespace']
        migrate_namespace(source_ns, target_ns)

if __name__ == "__main__":
    watch_migrations()
