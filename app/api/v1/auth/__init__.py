from fastapi import APIRouter

from . import login, logout, mfa, otp, password, register, social, token

router = APIRouter()

router.include_router(login.router)
router.include_router(logout.router)
router.include_router(mfa.router)
router.include_router(otp.router)
router.include_router(password.router)
router.include_router(register.router)
router.include_router(social.router)
router.include_router(token.router)

__all__ = ["router"]