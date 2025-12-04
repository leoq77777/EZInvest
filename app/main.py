"""
FastAPI应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
import logging

# 延迟导入router，避免在导入时就触发所有依赖
def get_router():
    """延迟加载router"""
    from app.api.routes import router
    return router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="EZInvest API",
    description="智能投资助手AI Agent API",
    version="0.1.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（延迟加载）
try:
    router = get_router()
    app.include_router(router)
except Exception as e:
    logger.warning(f"Failed to load API routes: {e}")

# 静态文件（前端）
try:
    from fastapi.responses import FileResponse
    import os
    
    @app.get("/", response_class=FileResponse)
    async def read_root():
        """返回前端页面"""
        return FileResponse("frontend/index.html")
    
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
except Exception as e:
    logger.warning(f"Frontend files not available: {e}")


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "message": "EZInvest API is running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    logger = logging.getLogger(__name__)
    logger.info("Starting EZInvest API...")
    
    # 启动数据预取调度器
    try:
        from app.services.prefetch_scheduler import prefetch_scheduler
        prefetch_scheduler.start()
        logger.info("Prefetch scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start prefetch scheduler: {e}")
    
    logger.info("EZInvest API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down EZInvest API...")
    
    try:
        from app.services.prefetch_scheduler import prefetch_scheduler
        prefetch_scheduler.stop()
    except:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

