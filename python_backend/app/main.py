

from fastapi import FastAPI, WebSocket, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.models import Task
from app.agent import app_agent
from app.websocket import manager
from langchain_core.messages import HumanMessage
import json
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware configured.")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up... creating DB tables if not exist.")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")

@app.get("/")
async def read_root():
    logger.info("Root endpoint hit.")
    return {"message": "Welcome to the AI-Powered Task Management Backend!"}

@app.get("/tasks")
async def get_all_tasks(db: Session = Depends(get_db)):
    logger.info("Received request to fetch all tasks.")
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    logger.info(f"Retrieved {len(tasks)} tasks from DB.")
    
    tasks_data = []
    for t in tasks:
        task_entry = {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status.value,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "priority": t.priority.value,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        logger.debug(f"Task: {task_entry}")
        tasks_data.append(task_entry)

    logger.info("Sending task list response.")
    return {"tasks": tasks_data}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    logger.info("WebSocket connection initializing...")
    await manager.connect(websocket)
    logger.info(f"WebSocket connected: {websocket.client}")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket data: {data}")

            message = json.loads(data)

            if message["type"] == "chat_message":
                user_message_content = message["content"]
                logger.info(f"Processing user message: {user_message_content}")

                chat_history = [HumanMessage(content=user_message_content)]
                logger.info("Invoking agent with chat history...")
                agent_output = await app_agent.ainvoke(
                    {"input": user_message_content, "chat_history": chat_history}
                )
                logger.info("Agent response received.")

                ai_response_content = "I'm processing your request..."
                tasks_updated_flag = False

                if "agent_outcome" in agent_output:
                    outcome = agent_output["agent_outcome"]
                    logger.info("Agent outcome found.")
                    
                    if isinstance(outcome, str):
                        ai_response_content = outcome
                        logger.info("Agent returned string response.")
                    elif isinstance(outcome, list) and all(isinstance(item, dict) for item in outcome):
                        logger.info(f"Processing list of tool responses ({len(outcome)} items).")
                        tool_messages = []

                        for item in outcome:
                            tool_name = item.get("tool_name", "unknown_tool")
                            response_data = item.get("response", {})
                            status_msg = response_data.get("status", "unknown")
                            message_msg = response_data.get("message", "No specific message.")

                            logger.info(f"Tool '{tool_name}' executed with status: {status_msg}")
                            tool_feedback = f"Tool '{tool_name}' executed: Status: {status_msg}, Message: {message_msg}"
                            tool_messages.append(tool_feedback)

                            if status_msg == "success" and "task" in response_data:
                                task_info = response_data["task"]
                                logger.info(f"Task created/updated by tool: {task_info}")
                                task_summary = f"Task details: Title: {task_info.get('title')}, Status: {task_info.get('status')}, Priority: {task_info.get('priority')}"
                                if task_info.get('id'):
                                    task_summary += f", ID: {task_info['id']}"
                                tool_messages.append(task_summary)
                            elif status_msg == "error":
                                logger.error(f"Error from tool '{tool_name}': {message_msg}")
                        ai_response_content = "\n".join(tool_messages)
                    else:
                        logger.warning(f"Unexpected agent_outcome format: {outcome}")
                        ai_response_content = "The agent had an unexpected outcome."

                if agent_output.get("tasks_updated", False):
                    logger.info("tasks_updated flag is True. Will refresh task list.")
                    tasks_updated_flag = True

                await manager.send_personal_message(json.dumps({
                    "type": "chat_message",
                    "sender": "agent",
                    "content": ai_response_content
                }), websocket)
                logger.info("Sent AI response to client.")

                if tasks_updated_flag:
                    logger.info("Preparing to send updated task list to all clients.")
                    await asyncio.sleep(0.05)
                    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
                    tasks_data = [
                        {
                            "id": t.id,
                            "title": t.title,
                            "description": t.description,
                            "status": t.status.value,
                            "due_date": t.due_date.isoformat() if t.due_date else None,
                            "priority": t.priority.value,
                            "created_at": t.created_at.isoformat(),
                            "updated_at": t.updated_at.isoformat(),
                        }
                        for t in tasks
                    ]
                    await manager.broadcast_json({
                        "type": "task_list_update",
                        "tasks": tasks_data
                    })
                    logger.info("Broadcasted updated task list to all connected clients.")

    except Exception as e:
        logger.exception(f"WebSocket Error for client {websocket.client}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "An unexpected error occurred. Please try again."
            })
        except RuntimeError:
            logger.warning("Failed to send error message to client.")
    finally:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")