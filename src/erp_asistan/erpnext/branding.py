"""Company branding across the ERPNext UI: navbar, login page, favicon, splash and printouts."""

from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["apply"]

_APP_SUFFIX = "ERP"
_LOGO_NAME = "logo.png"
_LOGO_HEIGHT_PX = 60
_NAVBAR = "Navbar Settings"
_WEBSITE = "Website Settings"
_SYSTEM = "System Settings"


def apply(c: ErpNextClient, company: str, logo: bytes | None) -> None:
    app_name = f"{company} {_APP_SUFFIX}"
    c.set_value(_SYSTEM, _SYSTEM, {"app_name": app_name})
    c.set_value(_WEBSITE, _WEBSITE, {"app_name": app_name, "title_prefix": app_name})
    if not logo:
        return

    url = c.upload(_LOGO_NAME, logo, "Company", company, "company_logo")
    c.set_value("Company", company, {"company_logo": url})
    c.set_value(_NAVBAR, _NAVBAR, {"app_logo": url})
    c.set_value(_WEBSITE, _WEBSITE, {"app_logo": url, "splash_image": url, "favicon": url, "banner_image": url})
    _letter_head(c, company, url)


def _letter_head(c: ErpNextClient, company: str, url: str) -> None:
    """Default letter head: printed quotations and invoices carry the logo."""
    vals = {"source": "Image", "image": url, "image_height": _LOGO_HEIGHT_PX, "align": "Left", "is_default": 1}
    if c.get_list("Letter Head", ["name"], filters=[["name", "=", company]], limit=1):
        c.set_value("Letter Head", company, vals)
        return

    c.insert({"doctype": "Letter Head", "letter_head_name": company, **vals})
