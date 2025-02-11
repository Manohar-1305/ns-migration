from kubernetes import client, config, watch
import os

try:
    # Automatically detect if running in a cluster or locally
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        config.load_incluster_config()  # Running inside a pod
        print("✅ Loaded in-cluster Kubernetes config")
    else:
        config.load_kube_config()  # Running locally
        print("✅ Loaded local kubeconfig")

    api = client.CustomObjectsApi()
    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()
    
    print("✅ Kubernetes client initialized")

except Exception as e:
    print(f"⚠️ Warning: Could not load Kubernetes configuration: {e}")
    api = None
    core_api = None
    apps_api = None

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

    # Migrate ConfigMaps 
    configmaps = core_api.list_namespaced_config_map(source_ns).items
    for cm in configmaps:
        if cm.metadata.name == "kube-root-ca.crt":
            continue  # Skip default Kubernetes ConfigMap
        
        cm.metadata.namespace = target_ns
        cm.metadata.resource_version = None
        core_api.create_namespaced_config_map(target_ns, cm)
    
    # Migrate Services
    services = core_api.list_namespaced_service(source_ns).items
    for svc in services:
        svc.metadata.namespace = target_ns
        svc.metadata.resource_version = None  # Reset resource version

        # Remove clusterIP to allow automatic assignment
        if svc.spec.cluster_ip:
            svc.spec.cluster_ip = None
        if svc.spec.clusterIPs:
            svc.spec.clusterIPs = None
        
        core_api.create_namespaced_service(target_ns, svc)
    
    print(f"✅ Migration completed from {source_ns} to {target_ns}")

def watch_migrations():
    if not api:
        print("❌ Kubernetes API client is not initialized. Exiting.")
        return
    
    w = watch.Watch()
    for event in w.stream(api.list_cluster_custom_object, CRD_GROUP, CRD_VERSION, CRD_PLURAL):
        migration = event['object']
        source_ns = migration['spec']['sourceNamespace']
        target_ns = migration['spec']['targetNamespace']
        migrate_namespace(source_ns, target_ns)

if __name__ == "__main__":
    watch_migrations()
