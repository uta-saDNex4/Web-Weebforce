"""Application entry point for the Contract Verifier API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import create_empty_database, get_db
from .routers.auth_routes import router as auth_router
from .routers.contract_routes import router as contract_router

# Create the database schema
create_empty_database()

# Initialize the FastAPI app
app = FastAPI(
    title="Contract Verifier API",
    description="Upload, xác thực hợp đồng, quản lý ảnh/biên lai và phân tích rủi ro AI.",
    version="1.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(contract_router)

# Health check endpoint
@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
