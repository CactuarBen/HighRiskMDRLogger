The only part of the system that contains permanent records.
Receives audit events, stores them in postgres database and allows audit to read them.

- Functions:
1) Receiving events from the forwarder, which sends it over POST request via HTTP
2) Signs each received event by computing HMAC-SHA256 over the key fields (event_id, timestamp, model_name, version, input_data_hash)
3) Stores the signed events by persisting them as an audit_logs into the SQLite or Postgres
4) Audit can read the events by accesing them as a GET /events/{id} or GET /events for all of them.

Prerequsities