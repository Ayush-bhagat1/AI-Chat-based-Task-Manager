
from sqlalchemy.orm import Session
from app.models import Task, TaskStatus, TaskPriority
from datetime import datetime
from typing import Optional, List, Dict, Union
from sqlalchemy import or_

def get_db_session_for_tool():
    from app.database import SessionLocal
    return SessionLocal()

def create_task(
    title: str,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[str] = None
) -> Dict[str, Union[str, int, bool, Dict]]:
    db = get_db_session_for_tool()
    try:
        parsed_due_date = None
        if due_date:
            try:
                parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                return {"status": "error", "message": "Invalid due_date format. Use YYYY-MM-DD."}

        parsed_priority = TaskPriority.MEDIUM
        if priority:
            try:
                parsed_priority = TaskPriority[priority.upper()]
            except KeyError:
                return {"status": "error", "message": f"Invalid priority: {priority}. Must be one of {list(TaskPriority)}."}

        new_task = Task(
            title=title,
            description=description,
            due_date=parsed_due_date,
            priority=parsed_priority,
            status=TaskStatus.TODO 
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return {"status": "success", "message": f"Task '{new_task.title}' created successfully with ID {new_task.id}.", "task": {
                "id": new_task.id,
                "title": new_task.title,
                "description": new_task.description,
                "status": new_task.status.value,
                "due_date": new_task.due_date.isoformat() if new_task.due_date else None,
                "priority": new_task.priority.value,
                "created_at": new_task.created_at.isoformat(),
                "updated_at": new_task.updated_at.isoformat(),
            }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to create task: {str(e)}"}
    finally:
        db.close()

def update_task(
    task_id: Optional[int] = None,
    title_match: Optional[str] = None,
    new_title: Optional[str] = None,
    new_description: Optional[str] = None,
    new_status: Optional[str] = None,
    new_due_date: Optional[str] = None,
    new_priority: Optional[str] = None
) -> Dict[str, Union[str, int, bool, Dict]]:
    db = get_db_session_for_tool()
    try:
        task = None
        if task_id:
            task = db.query(Task).filter(Task.id == task_id).first()
        elif title_match:
            task = db.query(Task).filter(Task.title.ilike(f"%{title_match}%")).first()

        if not task:
            return {"status": "error", "message": f"Task not found with ID {task_id or title_match}."}

        if new_title:
            task.title = new_title
        if new_description:
            task.description = new_description
        if new_status:
            try:
                task.status = TaskStatus[new_status.upper()]
            except KeyError:
                return {"status": "error", "message": f"Invalid status: {new_status}. Must be one of {list(TaskStatus)}."}
        if new_due_date:
            try:
                task.due_date = datetime.strptime(new_due_date, "%Y-%m-%d")
            except ValueError:
                return {"status": "error", "message": "Invalid new_due_date format. Use YYYY-MM-DD."}
        if new_priority:
            try:
                task.priority = TaskPriority[new_priority.upper()]
            except KeyError:
                return {"status": "error", "message": f"Invalid new_priority: {new_priority}. Must be one of {list(TaskPriority)}."}

        db.commit()
        db.refresh(task)
        return {"status": "success", "message": f"Task '{task.title}' updated successfully.", "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "priority": task.priority.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to update task: {str(e)}"}
    finally:
        db.close()

def delete_task(
    task_id: Optional[int] = None,
    title_match: Optional[str] = None
) -> Dict[str, Union[str, int, bool]]:
    db = get_db_session_for_tool()
    try:
        task = None
        if task_id:
            task = db.query(Task).filter(Task.id == task_id).first()
        elif title_match:
            task = db.query(Task).filter(Task.title.ilike(f"%{title_match}%")).first()

        if not task:
            return {"status": "error", "message": f"Task not found with ID {task_id or title_match}."}

        db.delete(task)
        db.commit()
        return {"status": "success", "message": f"Task '{task.title}' (ID: {task.id}) deleted successfully."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to delete task: {str(e)}"}
    finally:
        db.close()

def list_tasks() -> Dict[str, Union[str, List[Dict]]]:
    db = get_db_session_for_tool()
    try:
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
        return {"status": "success", "tasks": tasks_data}
    except Exception as e:
        return {"status": "error", "message": f"Failed to list tasks: {str(e)}"}
    finally:
        db.close()

def filter_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_date_before: Optional[str] = None,
    due_date_after: Optional[str] = None
) -> Dict[str, Union[str, List[Dict]]]:
    db = get_db_session_for_tool()
    try:
        query = db.query(Task)

        if status:
            try:
                query = query.filter(Task.status == TaskStatus[status.upper()])
            except KeyError:
                return {"status": "error", "message": f"Invalid status for filter: {status}. Must be one of {list(TaskStatus)}."}
        if priority:
            try:
                query = query.filter(Task.priority == TaskPriority[priority.upper()])
            except KeyError:
                return {"status": "error", "message": f"Invalid priority for filter: {priority}. Must be one of {list(TaskPriority)}."}
        if due_date_before:
            try:
                parsed_date = datetime.strptime(due_date_before, "%Y-%m-%d")
                query = query.filter(Task.due_date <= parsed_date)
            except ValueError:
                return {"status": "error", "message": "Invalid due_date_before format. Use YYYY-MM-DD."}
        if due_date_after:
            try:
                parsed_date = datetime.strptime(due_date_after, "%Y-%m-%d")
                query = query.filter(Task.due_date >= parsed_date)
            except ValueError:
                return {"status": "error", "message": "Invalid due_date_after format. Use YYYY-MM-DD."}

        tasks = query.order_by(Task.created_at.desc()).all()
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
        return {"status": "success", "tasks": tasks_data}
    except Exception as e:
        return {"status": "error", "message": f"Failed to filter tasks: {str(e)}"}
    finally:
        db.close()