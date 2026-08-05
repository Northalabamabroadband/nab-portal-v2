from __future__ import annotations
import base64, hashlib, hmac, json, time, uuid
from pathlib import Path
from typing import Any, Mapping
import httpx
from app.core.settings import get_settings
settings=get_settings()
class TAUCError(RuntimeError): pass
def compact_mac(value:str)->str: return "".join(c for c in value if c.isalnum()).upper()
def result_data(payload:Any)->dict[str,Any]:
    if not isinstance(payload,dict): return {}
    result=payload.get("result")
    return result if isinstance(result,dict) else {}
class TAUCClient:
    def __init__(self)->None:
        self.base_url=settings.tauc_base_url.rstrip("/"); self.access_key=settings.tauc_access_key.strip(); self.secret_key=settings.tauc_secret_key.strip(); self.client_cert=Path(settings.tauc_client_cert); self.client_key=Path(settings.tauc_client_key); self.verify_tls=settings.tauc_verify_tls; self.timeout=settings.tauc_timeout_seconds
    def configured(self)->bool: return bool(self.base_url and self.access_key and self.secret_key and self.client_cert.is_file() and self.client_key.is_file())
    def _body(self,payload:Any)->bytes: return json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode()
    def _authorization(self,path:str,body:bytes|None)->tuple[str,str|None]:
        timestamp=str(int(time.time())); nonce=str(uuid.uuid4()); parts=[]; md5=None
        if body: md5=base64.b64encode(hashlib.md5(body).digest()).decode(); parts.append(md5)
        parts.extend((timestamp,nonce,path)); signature=hmac.new(self.secret_key.encode(),"\n".join(parts).encode(),hashlib.sha256).hexdigest()
        return f"Nonce={nonce},AccessKey={self.access_key},Signature={signature},Timestamp={timestamp}",md5
    async def request(self,method:str,path:str,*,params:Mapping[str,Any]|None=None,json_data:Any=None,extra_headers:Mapping[str,str]|None=None)->Any:
        if not self.configured(): raise TAUCError("TAUC access key, secret key, and mTLS certificate/key are required")
        path=path if path.startswith("/") else f"/{path}"; body=self._body(json_data) if json_data is not None else None; auth,md5=self._authorization(path,body); headers={"Accept":"application/json","X-Authorization":auth}
        if body is not None: headers.update({"Content-Type":"application/json","Content-MD5":md5 or ""})
        if extra_headers: headers.update(extra_headers)
        async with httpx.AsyncClient(cert=(str(self.client_cert),str(self.client_key)),verify=self.verify_tls,timeout=self.timeout,follow_redirects=True) as client:
            try: response=await client.request(method.upper(),f"{self.base_url}{path}",params=params,headers=headers,content=body)
            except httpx.HTTPError as exc: raise TAUCError(f"Unable to reach TAUC: {exc}") from exc
        try: payload=response.json() if response.content else {}
        except ValueError as exc: raise TAUCError(f"TAUC returned invalid JSON (HTTP {response.status_code})") from exc
        if response.status_code>=400 or (isinstance(payload,dict) and payload.get("errorCode") not in (None,0,"0")):
            code=payload.get("errorCode",response.status_code) if isinstance(payload,dict) else response.status_code; message=payload.get("msg",response.reason_phrase) if isinstance(payload,dict) else response.reason_phrase; raise TAUCError(f"TAUC error {code}: {message}")
        return payload
    async def get_device_id(self,serial_number:str,mac_address:str)->str:
        payload=await self.request("GET","/v1/openapi/device-information/device-id",params={"sn":serial_number.strip(),"mac":compact_mac(mac_address)}); device_id=str(result_data(payload).get("deviceId") or "")
        if not device_id: raise TAUCError("TAUC did not return a device ID")
        return device_id
    async def device_info(self,device_id:str)->Any: return await self.request("GET",f"/v1/openapi/device-information/device-info/{device_id}")
    async def device_lookup(self,*,serial_number:str,mac_address:str|None=None)->dict[str,Any]:
        if not mac_address: raise TAUCError("TAUC lookup requires serial number and MAC")
        device_id=await self.get_device_id(serial_number,mac_address); payload=await self.device_info(device_id); return {**result_data(payload),"deviceId":device_id,"sn":serial_number,"mac":compact_mac(mac_address)}
    async def network_lookup(self,*,serial_number:str,mac_address:str|None=None)->dict[str,Any]:
        device=await self.device_lookup(serial_number=serial_number,mac_address=mac_address); return {"networkId":str(device.get("networkId") or device.get("networkID") or ""),"deviceId":device.get("deviceId"),"device":device}
    async def wifi_ssid(self,device_id:str)->Any: return await self.request("GET",f"/v1/openapi/device-management/aginet/wifi-ssid/{device_id}",params={"refresh":"true"})
    async def wifi_password(self,device_id:str)->Any: return await self.request("GET",f"/v1/openapi/device-management/aginet/wifi-password/{device_id}",params={"refresh":"true"},extra_headers={"Required-Network-Control-Access":"false","Disposable-Network-Control-Access":"true"})
    async def connection_status(self)->dict[str,Any]:
        status={"configured":self.configured(),"connected":None,"base_url":self.base_url,"authentication_mode":"mtls-aksk-x-authorization","certificate_present":self.client_cert.is_file(),"private_key_present":self.client_key.is_file(),"access_key_configured":bool(self.access_key),"secret_key_configured":bool(self.secret_key)}
        if self.configured() and settings.tauc_test_serial_number and settings.tauc_test_mac_address:
            try:
                device=await self.device_lookup(serial_number=settings.tauc_test_serial_number,mac_address=settings.tauc_test_mac_address); status.update({"connected":True,"device_id":device.get("deviceId"),"network_id":device.get("networkId"),"device_model":device.get("deviceModel") or device.get("model")})
            except TAUCError as exc: status.update({"connected":False,"detail":str(exc)})
        else: status["detail"]="Set TAUC_TEST_SERIAL_NUMBER and TAUC_TEST_MAC_ADDRESS for a live lookup test"
        return status
