# HighRiskMDRLogger
A standalone prototype for logging the runtime events of the AI-enabled Medical Devices. Satisfies the EU AI Act, MDR (MDAI 2025), GDPR, PLD directives. Subjected to changes.

# Components
The components should be exported into the project under question via little to no changes, the only element that requires configuration is the compliance adapter that is meant to receive the desired outputs from the AI-enabled application

## Project Specific Adapter (01-compliance-adapter)
A dummy adapter for the existing projects, that would attach to the main application doing processing, and demonstrating the contract against a real framework.

## Compliance Logging SDK (02-compliance-logging-sdk)
The interceptor SDK, which contains the ComplianceLogger and a @trace decorator, as well as the Objects that would contain the necessary data, namely: ComplianceObject, SystemMetadata, ClinicalSession, InferenceResult. No network code in contained in this component, every captured event is written to a local append-only queue that is later polled. Automated tests were created to perform static-analysis test scans the files for any existing import statements dealing with connectivity and then fails to build if it detects any.

## Compliance Forwarder (03-compliance-forwarder)
The compliance forwarder is a standalone Python process that polls the SDK’s local queue. Once the payload is captured, it uses an HTTP post call to deliver the events to the backend. The queue is durable, meaning that if the forwarder crashes, the events will still be captured in the pipeline for some time, ideally alerting/halting processing. Transient failures (connectivity errors, timeouts, 500 errors) are later re-tried with a continuously increasing time gap between them. If a 400 response is received, then the event would be sent to the deadletter queue, since retrying that specific payload would fail identically forever and block the events that were following it.

## Compliance Backend (04-compliance-backend)
The compliance sidecar, which is a FastAPI service that exposes the audit, metadata, oversight endpoint groups, computing a SHA-256 signature for the included fields in the event, storing them in a single audit_logs table.