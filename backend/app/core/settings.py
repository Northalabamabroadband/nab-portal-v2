from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "production"
    app_name: str = "NAB Mission Control"
    app_version: str = "2.0.0-rc1-build021"
    app_secret_key: str
    database_url: str
    redis_url: str
    cors_origins: str = ""
    log_level: str = "INFO"
    session_ttl_seconds: int = 43200
    bootstrap_admin_email: str = "admin@nabroadband.com"
    bootstrap_admin_password: str = "change-this-immediately"

    uisp_base_url: str = Field(default="", validation_alias=AliasChoices("UISP_BASE_URL", "UISP_URL", "UISP_CRM_URL"))
    uisp_api_token: str = Field(default="", validation_alias=AliasChoices("UISP_API_TOKEN", "UISP_TOKEN", "UISP_CRM_API_TOKEN", "UISP_CRM_TOKEN"))
    uisp_crm_base_url: str = ""
    uisp_crm_api_token: str = ""
    uisp_nms_base_url: str = Field(default="", validation_alias=AliasChoices("UISP_NMS_BASE_URL", "UISP_NETWORK_URL", "UISP_NMS_URL"))
    uisp_nms_api_token: str = Field(default="", validation_alias=AliasChoices("UISP_NMS_API_TOKEN", "UISP_NETWORK_TOKEN", "UISP_NMS_TOKEN"))
    uisp_verify_tls: bool = False
    uisp_timeout_seconds: float = 20.0
    uisp_auth_mode: str = "app-key"
    uisp_crm_auth_mode: str = ""
    uisp_nms_auth_mode: str = ""
    uisp_crm_clients_path: str = "/crm/api/v1.0/clients"
    uisp_crm_invoices_path: str = "/crm/api/v1.0/invoices"
    uisp_crm_payments_path: str = "/crm/api/v1.0/payments"
    uisp_nms_devices_path: str = "/nms/api/v2.1/devices"
    uisp_nms_sites_path: str = "/nms/api/v2.1/sites"

    tauc_base_url: str = Field(default="https://use1-tauc-openapi.tplinkcloud.com", validation_alias=AliasChoices("TAUC_BASE_URL", "TAUC_API_BASE_URL", "TAUC_URL"))
    tauc_access_key: str = Field(default="", validation_alias=AliasChoices("TAUC_ACCESS_KEY", "TAUC_API_ACCESS_KEY", "TAUC_APP_KEY"))
    tauc_secret_key: str = Field(default="", validation_alias=AliasChoices("TAUC_SECRET_KEY", "TAUC_API_SECRET_KEY", "TAUC_APP_SECRET"))
    tauc_client_cert: str = "/run/secrets/tauc/client.crt"
    tauc_client_key: str = "/run/secrets/tauc/client.key"
    tauc_verify_tls: bool = True
    tauc_timeout_seconds: float = 20.0
    tauc_min_request_interval_seconds: float = 1.05
    tauc_test_serial_number: str = ""
    tauc_test_mac_address: str = ""
    tauc_network_clients_path: str = ""
    tauc_wifi_ssid_read_path: str = "/v1/openapi/device-management/aginet/wifi-ssid"
    tauc_device_lookup_path: str = "/v1/openapi/device-information/device-id"
    tauc_network_lookup_path: str = "/v1/openapi/device-information/device-info"
    tauc_wifi_ssid_update_path: str = ""
    tauc_wifi_password_update_path: str = ""
    tauc_reboot_path: str = ""
    tauc_diagnostics_path: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
