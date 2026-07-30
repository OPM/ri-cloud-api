# ri-cloud-api

A local-hosted backend service that bridges [Sumo](https://github.com/equinor/fmu-sumo)
data into [ResInsight](https://resinsight.org) (and other local clients) over a
small FastAPI HTTP API.

## Packages

### `ri_cloud_api` — main application
The FastAPI application under `ri_cloud_api/primary/`:
* Route definitions (HTTP endpoints) under `primary/routers` — `explore`, `timeseries`, `surfaces`, `polygons`, `grids` and `parameters`
* Application setup and configuration
* Serves as the entry point for the backend

The Pydantic models defining the request/response contracts live alongside each
router in `primary/routers/<area>/schemas.py`.

### `ri_cloud_api/libs` — shared libraries
Reusable packages used across the application, located under `ri_cloud_api/libs/`:

* `ri_cloud_services` (`libs/services/src/ri_cloud_services`) — the service layer, responsible for:
    * Accessing data from Sumo via `fmu-sumo` (see `sumo_access/`)
    * Assembling and transforming data
    * Isolating business logic from the API layer

* `ri_cloud_core_utils` (`libs/core_utils/src/ri_cloud_core_utils`) — general-purpose utilities:
    * Lightweight helpers with minimal external dependencies
    * Does not depend on framework or service-layer code

**Dependency direction**:
`ri_cloud_api` → `ri_cloud_services` → `ri_cloud_core_utils`

## Development setup
Dependencies are managed with [uv](https://docs.astral.sh/uv/) and defined in
`pyproject.toml`. From the repository root:

```bash
# 1. Install uv (see https://docs.astral.sh/uv/getting-started/installation/)

# 2. Install the project and its dependencies (creates .venv automatically)
uv sync
```

The first `uv sync` generates `uv.lock`; commit that file.

## Running the service
Start the API with uvicorn from the repository root:

```cmd
uv run uvicorn ri_cloud_api.primary.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation is then available at:

* Swagger UI: http://localhost:8000/docs
* ReDoc: http://localhost:8000/redoc

## Configuration
* `RI_CLOUD_API_SUMO_ENV` - Sumo environment to connect to (defaults to `prod`).
