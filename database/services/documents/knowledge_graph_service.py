import uuid
import networkx as nx
import os
from pyvis.network import Network

from services.ai.mistral_service import MistralService


class KnowledgeGraphService:

    @staticmethod
    def generate_graph(text: str, source_file: str = None):
        file_type = (
      os.path.splitext(source_file)[1].replace(".", "")
      if source_file else "unknown"
  )

        prompt = f"""

You are an Enterprise AI Operational Intelligence & Knowledge Graph Extraction Engine.

Your responsibility is to analyze enterprise documents and generate a highly connected operational knowledge graph representing:

- business workflows

- ITSM operations

- SLA intelligence

- customer-service relationships

- escalation chains

- support operations

- governance structures

- compliance dependencies

- risk propagation

- technical infrastructure

- AI operational context

- service dependencies

- enterprise architecture



━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL INSTRUCTIONS

━━━━━━━━━━━━━━━━━━━━━━━



1. RETURN ONLY VALID JSON.



2. DO NOT RETURN:

- markdown

- explanations

- notes

- comments

- summaries

- headings

- extra text



3. RESPONSE MUST CONTAIN ONLY:

- nodes

- edges



4. STRICTLY FOLLOW THIS JSON STRUCTURE:



{{

  "nodes": [

    {{

      "id": "Ticket",

      "type": "entity_type",

      "description": "Short description"

    }}

  ],

  "edges": [

    {{

      "from": "Customer",

      "to": "Ticket",

      "relation": "raises",

      "strength": "high"

    }}

  ]

}}



5. ENSURE JSON IS VALID AND PARSEABLE.



━━━━━━━━━━━━━━━━━━━━━━━

GRAPH GENERATION RULES

━━━━━━━━━━━━━━━━━━━━━━━



6. Build a FULLY CONNECTED multi-hop knowledge graph.



GOOD EXAMPLE:

Customer

→ raises

→ Ticket

→ assigned_to

→ L1 Support

→ escalates_to

→ L2 Support

→ reports_to

→ Service Manager

→ audited_by

→ Audit Head



7. Every node MUST participate in at least one relationship whenever possible.



8. Avoid isolated/disconnected nodes.



9. Infer hidden operational relationships intelligently from context.



10. Deduplicate entities intelligently.



Example:

- PostgreSQL

- Postgres

- postgres db



Should become ONE entity.



11. Extract relationships even if they are implied but not explicitly stated.



12. Build deep operational chains and dependency paths.



13. Prefer operational intelligence over isolated entity extraction.



━━━━━━━━━━━━━━━━━━━━━━━

ENTITY EXTRACTION RULES

━━━━━━━━━━━━━━━━━━━━━━━



Extract ALL meaningful enterprise entities dynamically.



Possible entity categories include but are NOT limited to:



BUSINESS ENTITIES:

- customer

- end user

- organization

- contract

- vendor

- stakeholder

- business unit



ITSM ENTITIES:

- ticket

- incident

- problem

- change request

- request

- escalation

- approval workflow

- SLA

- CSAT

- RCA

- audit report



SUPPORT & GOVERNANCE ENTITIES:

- L1 support

- L2 support

- support engineer

- support group

- resolver team

- service manager

- audit head

- compliance officer



RISK & COMPLIANCE ENTITIES:

- risk score

- compliance framework

- audit log

- SLA breach

- security incident

- regulatory exposure

- operational risk

- business impact

- financial exposure

- reputation risk



AI & CONTEXT ENTITIES:

- sentiment score

- escalation probability

- SLA breach probability

- resolution confidence

- historical incidents

- predictive risk

- incident timeline



TECHNICAL ENTITIES:

- applications

- APIs

- microservices

- databases

- cloud resources

- Kubernetes

- CI/CD

- authentication systems

- monitoring tools

- observability platforms

- schedulers

- workflows

- integrations

- storage

- networks

- deployment tools

- security tools

- infrastructure



KNOWLEDGE & OPERATIONS:

- knowledge base

- runbook

- alert

- log

- monitoring system

- CMDB

- dependency mapping

- deployment pipeline



━━━━━━━━━━━━━━━━━━━━━━━

RELATIONSHIP EXTRACTION RULES

━━━━━━━━━━━━━━━━━━━━━━━



Use concise enterprise-grade relationship names.



GOOD RELATIONSHIP EXAMPLES:



WORKFLOW RELATIONSHIPS:

- raises

- creates

- assigned_to

- handled_by

- escalates_to

- resolved_by

- reviewed_by

- approved_by

- audited_by

- monitored_by



OPERATIONAL RELATIONSHIPS:

- depends_on

- impacts

- blocks

- mitigates

- correlates_with

- governed_by

- validated_by

- tracked_by

- managed_by

- reported_to



TECHNICAL RELATIONSHIPS:

- communicates_with

- authenticates_with

- deployed_on

- stores_data_in

- monitored_by

- triggers

- integrates_with

- connects_to

- calls



RISK & SLA RELATIONSHIPS:

- increases_risk_for

- reduces_risk_for

- predicts

- influences

- violates

- governed_by

- causes

- escalates

- impacts_sla

- generates_alert_for



COMPLIANCE RELATIONSHIPS:

- complies_with

- governed_by

- validated_by

- audited_under

- reviewed_against



━━━━━━━━━━━━━━━━━━━━━━━

RISK & OPERATIONAL INTELLIGENCE

━━━━━━━━━━━━━━━━━━━━━━━



Infer operational intelligence relationships whenever possible.



Examples:



VIP Customer

→ increases_risk_for

→ Business Impact



Security Incident

→ impacts

→ Compliance Risk



High Sentiment Score

→ increases

→ Escalation Probability



SLA Near Breach

→ triggers

→ Escalation



Production Outage

→ impacts

→ Revenue



Compliance Framework

→ governs

→ Ticket Resolution



L2 Support

→ resolves

→ Critical Incident



Audit Head

→ validates

→ SLA Compliance



━━━━━━━━━━━━━━━━━━━━━━━

TEMPORAL & LIFECYCLE INTELLIGENCE

━━━━━━━━━━━━━━━━━━━━━━━



Extract lifecycle and workflow progression relationships.

Examples:

Customer

→ creates

→ Ticket

Ticket

→ assigned_to

→ L1 Support

L1 Support

→ escalates_to

→ L2 Support

L2 Support

→ resolves

→ Incident

Service Manager

→ reviews

→ SLA Metrics

Audit Head

→ audits

→ Compliance Process

━━━━━━━━━━━━━━━━━━━━━━━
AI CONTEXT ENRICHMENT
━━━━━━━━━━━━━━━━━━━━━━━

Extract entities and relationships useful for:

- AI copilots

- risk prediction

- SLA breach prediction

- root cause analysis

- impact analysis

- operational analytics

- graph RAG

- dependency intelligence

- incident triage

- escalation prediction

Prioritize extraction of:

- customer criticality

- business impact

- urgency

- severity

- compliance exposure

- operational dependency

- infrastructure impact

- financial exposure

- escalation likelihood

- resolution confidence

━━━━━━━━━━━━━━━━━━━━━━━
GRAPH QUALITY REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━

14. Return MINIMUM:

- 15 nodes

- 20 edges

15. Ensure graph density and connectivity.

16. Prefer multi-hop operational chains.

17. Ensure both:
- technical relationships
- business operational relationships

18. Capture:

- workflow hierarchy

- escalation hierarchy

- governance hierarchy

- service dependencies

- SLA dependencies

- risk propagation

19. Include relationship strength:
- low
- medium
- high
- critical
20. Node descriptions must be concise and meaningful.
21. Avoid duplicate edges.
22. Avoid generic meaningless nodes.

BAD:
- system
- platform
- service

GOOD:
- Payment Gateway
- SLA Engine
- Customer Portal
- Audit Service

━━━━━━━━━━━━━━━━━━━━━━━
FINAL OUTPUT REQUIREMENT
━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY VALID JSON.

DO NOT RETURN ANYTHING ELSE.

DOCUMENT:

{text[:15000]}

"""

        graph_data = MistralService.analyze_incident(
            prompt
        )
        import json

        if isinstance(graph_data, str):

            try:
                graph_data = json.loads(graph_data)

            except Exception as e:

                print("GRAPH JSON PARSE ERROR =", e)
                print("RAW RESPONSE =", graph_data)

                graph_data = {
                    "nodes": [],
                    "edges": []
                }

        print("FINAL GRAPH DATA =", graph_data)

        graph_url = (
            KnowledgeGraphService
            .generate_html_graph(graph_data)
        )

        graph_data["graph_url"] = graph_url

        graph_data["source_file"] = source_file
        graph_data["file_type"] = file_type

        return graph_data

    @staticmethod
    def generate_html_graph(graph_data: dict):

        graph_id = str(uuid.uuid4())[:8]

        filename = f"graph_{graph_id}.html"

        save_path = f"graphs/{filename}"

        G = nx.DiGraph()

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        for node in nodes:

          node_type = node.get("type", "").lower()

          color_map = {
              "customer": "#00C853",
              "end_user": "#00C853",
              "ticket": "#FFB300",
              "incident": "#FF7043",
              "sla": "#7E57C2",
              "support": "#42A5F5",
              "l1_support": "#42A5F5",
              "l2_support": "#1E88E5",
              "service_manager": "#EC407A",
              "audit": "#EF5350",
              "compliance": "#AB47BC",
              "risk": "#FFA726",
              "database": "#26A69A",
              "api": "#29B6F6",
              "application": "#66BB6A",
              "monitoring": "#5C6BC0",
              "knowledge_base": "#26C6DA",
              "security": "#EF5350",
              "workflow": "#8D6E63"
          }

          node_color = color_map.get(node_type, "#90A4AE")

          G.add_node(
              node["id"],
              label=node["id"],
              title=f'{node.get("type", "")}\n{node.get("description", "")}',
              color=node_color,
              size=25,
              font={"color": "white", "size": 16}
          )

        for edge in edges:

          relation = edge.get("relation", "").lower()

          edge_color_map = {
              "raises": "#00E676",
              "assigned_to": "#42A5F5",
              "escalates_to": "#FF7043",
              "depends_on": "#AB47BC",
              "monitored_by": "#26C6DA",
              "governed_by": "#EC407A",
              "audited_by": "#EF5350",
              "communicates_with": "#29B6F6",
              "stores_data_in": "#26A69A",
              "impacts": "#FFA726",
              "calls": "#5C6BC0"
          }

          edge_color = edge_color_map.get(relation, "#B0BEC5")

          G.add_edge(
              edge["from"],
              edge["to"],
              title=relation,
              label=relation,
              color=edge_color
          )

        net = Network(
            height="100vh",
            width="100%",
            bgcolor="#0B0F19",
            font_color="white",
            directed=True,
            notebook=False
        )

        net.from_nx(G)

        net.set_options("""
          var options = {
            "nodes": {
              "shape": "dot",
              "scaling": {
                "min": 20,
                "max": 40
              },
              "font": {
                "size": 16,
                "color": "white"
              }
            },
            "edges": {
              "color": {
                "inherit": false
              },
              "smooth": {
                "type": "dynamic"
              },
              "font": {
                "size": 12,
                "align": "middle"
              },
              "arrows": {
                "to": {
                  "enabled": true
                }
              }
            },
            "physics": {
              "enabled": true,
              "barnesHut": {
                "gravitationalConstant": -3000,
                "centralGravity": 0.2,
                "springLength": 180,
                "springConstant": 0.04,
                "damping": 0.09
              },
              "minVelocity": 0.75
            }
          }
          """)
        

        net.save_graph(save_path)

        return (
            f"http://122.163.121.176:3019/graphs/{filename}"
        )