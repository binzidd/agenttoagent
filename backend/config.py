"""
Centralised settings – all values read from environment / .env file.
No hardcoded secrets or site-specific values in code.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Home
    home_lat: float = -33.93
    home_lon: float = 150.82
    home_postcode: str = "2179"
    solar_system_kw: float = 9.0
    battery_capacity_kwh: float = 9.0
    feed_in_tariff_cents: float = 5.0

    # Bike
    bike_consumption_l_100km: float = 7.5
    bike_tank_fill_litres: float = 15.0
    preferred_fuel_type: str = "P98"

    # Anthropic – required for chat and ClaudeAdvisor
    anthropic_api_key: str = ""

    # NSW FuelCheck (optional – fallback to synthetic data if absent)
    nsw_fuelcheck_api_key: str = ""
    nsw_fuelcheck_api_secret: str = ""

    # CORS
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    def get_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
