from flask import Flask, Response
import requests
import json
from urllib.parse import quote

app = Flask(__name__)

# Konfiguration: mehrere WebLogic-Instanzen
WEBLOGIC_INSTANCES = [
    {
        "name": "domain1",
        "host": "http://weblogic1:7001",
        "auth": ("weblogic", "pass1"),
    },
    {
        "name": "domain2",
        "host": "http://weblogic2:7001",
        "auth": ("weblogic", "pass2"),
    }
]

JMSSERVER = "JMSServer-MsgBroker"

QUEUES = [
    "OrderMgmtMessageQueue",
    "OrderMgmt-ErrorMessageQueue",
    "OrderMgmtBioEvaluatorMessageQueue",
]

def get_queue_messages(host, auth, instance_name, queue_name):
    encoded_jms_server = quote(JMSSERVER)
    encoded_queue_name = quote(queue_name)

    url = f"{host}/management/weblogic/latest/domainRuntime/serverRuntimes/MsgBroker_1/JMSRuntime/JMSServers/{encoded_jms_server}/destinations/SystemModule-MsgBroker!{encoded_jms_server}@{encoded_queue_name}"

    try:
        response = requests.get(url, auth=auth, timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "queue": queue_name,
            "messagesCurrentCount": data.get("messagesCurrentCount", 0),
            "instance": instance_name
        }
    except requests.exceptions.RequestException as e:
        return {
            "queue": queue_name,
            "error": str(e),
            "instance": instance_name
        }

def discover_queues(weblogic_host, auth, server_name, jms_server):
    url = f"{weblogic_host}/management/weblogic/latest/domainRuntime/serverRuntimes/{server_name}/JMSRuntime/JMSServers/{jms_server}/destinations"
    try:
        response = requests.get(url, auth=auth, timeout=5)
        response.raise_for_status()
        data = response.json()
        return [entry["name"] for entry in data.get("items", [])]
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der Queues: {e}")
        return []

@app.route("/metrics")
def prometheus_metrics():
    metrics = []

    for instance in WEBLOGIC_INSTANCES:
        for queue in QUEUES:
            result = get_queue_messages(instance["host"], instance["auth"], instance["name"], queue)

            if "error" in result:
                print(f"[ERROR] {result['instance']}::{result['queue']} - {result['error']}")
                continue

            # Prometheus-Metrik
            metrics.append(
                f'weblogic_jms_messages_current{{queue="{result["queue"]}",instance="{result["instance"]}"}} {result["messagesCurrentCount"]}'
            )

    return Response("\n".join(metrics) + "\n", mimetype="text/plain; version=0.0.4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9100)
