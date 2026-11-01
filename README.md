# HighRiskMDRLogger
A standalone prototype for logging the runtime events of the AI-enabled Medical Devices. Satisfies the EU AI Act, MDR (MDAI 2025), GDPR, PLD directives. Subjected to changes.

# Components
The components should be exported into the project under question via little to no changes, the only element that requires configuration is the compliance adapter that is meant to receive the desired outputs from the AI-enabled application

## Project Specific Adapter (01-compliance-adapter)
A dummy adapter for the existing projects, that would attach to the main application doing processing, and demonstrating the contract against a real framework.

## Compliance Logging SDK (02-compliance-logging-sdk)
The interceptor SDK, which contains the ComplianceLogger and a @trace decorator, as well as the Objects that would contain the necessary data, namely: ComplianceObject, SystemMetadata, ClinicalSession, InferenceResult. No network code in contained in this component, every captured event is written to a local append-only queue that is later polled. Automated tests were created to perform static-analysis test scans the files for any existing import statements dealing with connectivity and then fails to build if it detects any.

### Sample output into the jsonl queue of ComplianceLogger.write_event:
```json
{"event_id":"131a2c6d-e9b3-4e1f-933b-70d36eb2a2f3","timestamp":"2026-10-29T00:41:23.391853Z","system":{"model_name":"demo-model","model_version":"1.0"},"clinical_session":{"input_data_hash":"sha256-2277f3ddd80c30d9a85a324facb482ab3c54062a30ebcf7956c4dc57670b82b2","inference_result":{"prediction":{"label":"healthy"},"confidence":0.79,"execution_time_ms":0.02968098851852119}}}
{"event_id":"831f1b80-7a02-484c-b03f-5ea61d613fc3","timestamp":"2026-10-29T00:41:23.391931Z","system":{"model_name":"demo-model","model_version":"1.0"},"clinical_session":{"input_data_hash":"sha256-c9220da099ae6381db577037e305d7ca942fa84609aa631471c6973a75d29485","inference_result":{"prediction":{"label":"tumor"},"confidence":0.67,"execution_time_ms":0.008660004823468626}}}
```

## Compliance Forwarder (03-compliance-forwarder)
The compliance forwarder is a standalone Python process that polls the SDK’s local queue. Once the payload is captured, it uses an HTTP post call to deliver the events to the backend. The queue is durable, since it is a jsonl file that remains in place, meaning that if the forwarder crashes, the events will still be captured in the file for some time and rendered unprocessed, ideally alerting/halting processing. 

2XX responses successfully deliver the payload to backend

Transient failures (connectivity errors, timeouts, 500 errors) are later re-tried with a continuously increasing time gap between them. 

If a 400 response is received, then the event would be sent to the deadletter queue, since retrying that specific payload would fail identically forever and block the events that were following it.

1XX, 3XX and other responses are treated as warnings and processed same as transient issues (retry in some time)


## Compliance Backend (04-compliance-backend)  - main service 
The only part of the system that holds permanent records. 
It is a FastAPI service that gets the events from the forwarder, signs them, stores them and then an auditor can request them.

Chain of events:
1) Receives events through `POST /events` accepts the JSON the SDK wrote to the queue.
2) Ignores duplicates by checking `event_id`,so that the forwarder can resend an event after a timeout or a crash.
3) Signs each new event with HMAC-SHA256 signature over `event_id`, `timestamp`, `model_name`, `model_version` and `input_data_hash`, computed with a secret key stored at `SIGNING_KEY` env var. Without the key nobody can produce a matching signature, so a stored row that was changed no longer matches its signature.
4) Persists the event into a relational db. One row per event in the `audit_logs` table (SQLite, file `audit.db`).
5) Makes it possible to retrieve a specific id by eventId or all events

| Route | Answer |
|---|---|
| `POST /events` | `201` with the stored event, including its `signature` |
| `GET /events/{event_id}` | `200` with the event, `404` if the id is unknown |
| `GET /events` | `200` with all events, newest first |

Run it from the folder where `audit.db` should live:
```bash
SIGNING_KEY=<your secret> uvicorn compliance_backend.main:app --port 8000
```