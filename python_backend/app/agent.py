import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Union
import operator
from app.config import settings
from app import tools
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("LangGraphAgent")

tools_list = [
    tools.create_task,
    tools.update_task,
    tools.delete_task,
    tools.list_tasks,
    tools.filter_tasks,
]
logger.info(f"🧰 Registered tools: {[tool.__name__ for tool in tools_list]}")

logger.info("🔧 Initializing Gemini Pro LLM...")
llm_base = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key= os.getenv("GEMINI_API_KEY")

)

llm = llm_base.bind_tools(tools_list)
logger.info("✅ LLM Initialized with tools bound.")

def execute_tool(tool_name: str, tool_args: dict):
    logger.info(f"🚀 Executing tool: {tool_name} with args: {tool_args}")
    try:
        tool_func = getattr(tools, tool_name)
        result = tool_func(**tool_args)
        logger.info(f"✅ Tool '{tool_name}' executed successfully.")
        return result
    except Exception as e:
        logger.exception(f"❌ Tool '{tool_name}' execution failed.")
        return {"status": "error", "message": f"Tool execution failed: {e}"}

class AgentState(TypedDict):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, ToolMessage]]
    agent_outcome: Union[str, List[dict], None]
    tool_calls: List[dict]
    tasks_updated: bool

def call_model(state: AgentState):
    logger.info("🧠 [Model Node] Invoking LLM...")
    
    messages = state["chat_history"].copy()
    
    current_input = state["input"]
    if not messages or not isinstance(messages[-1], HumanMessage) or messages[-1].content != current_input:
        messages.append(HumanMessage(content=current_input))
    
    logger.info(f"📝 Sending {len(messages)} messages to LLM")
    for i, msg in enumerate(messages):
        logger.info(f"   Message {i}: {type(msg).__name__} - {msg.content[:100]}...")
    
    response = llm.invoke(messages)
    logger.info("✅ LLM invocation complete.")

    updated_chat_history = messages.copy()

    tool_calls = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info(f"🔍 LLM requested {len(response.tool_calls)} tool(s).")
        for tc in response.tool_calls:
            logger.info(f"📌 Tool Call: {tc['name']} | Args: {tc['args']}")
            tool_calls.append({
                "name": tc['name'],
                "args": tc['args'],
                "id": tc['id']
            })
        
        updated_chat_history.append(AIMessage(content=response.content or "", tool_calls=response.tool_calls))
        
        return {
            "agent_outcome": None,
            "tool_calls": tool_calls,
            "chat_history": updated_chat_history
        }
    else:
        logger.info("📨 Direct response from LLM (no tools).")
        updated_chat_history.append(AIMessage(content=response.content))
        return {
            "agent_outcome": response.content,
            "tool_calls": [],
            "chat_history": updated_chat_history
        }

def call_tool(state: AgentState):
    logger.info("🔧 [Tool Node] Executing tools from LLM request.")
    tool_calls = state["tool_calls"]
    responses = []
    tasks_updated = False
    
    updated_chat_history = state["chat_history"].copy()

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        try:
            tool_response = execute_tool(tool_name, tool_args)
            logger.info(f"📦 Tool '{tool_name}' executed with result: {tool_response}")
            responses.append({"tool_name": tool_name, "response": tool_response})
            
            updated_chat_history.append(ToolMessage(
                content=str(tool_response), 
                tool_call_id=tool_id
            ))
            
            if tool_name in ["create_task", "update_task", "delete_task"]:
                tasks_updated = True
                
        except Exception as e:
            logger.exception(f"🔥 Exception while executing tool '{tool_name}'.")
            error_response = {"status": "error", "message": f"Tool execution failed: {e}"}
            responses.append({"tool_name": tool_name, "response": error_response})
            
            updated_chat_history.append(ToolMessage(
                content=str(error_response), 
                tool_call_id=tool_id
            ))
    
    logger.info("✅ Tool execution complete.")
    return {
        "agent_outcome": responses,
        "tasks_updated": tasks_updated,
        "chat_history": updated_chat_history
    }

def should_continue(state: AgentState):
    if state.get("tool_calls") and len(state["tool_calls"]) > 0:
        return "tool"
    else:
        return END

logger.info("🔗 Creating agent workflow graph...")
workflow = StateGraph(AgentState)
workflow.add_node("model", call_model)
workflow.add_node("tool", call_tool)
workflow.set_entry_point("model")

workflow.add_conditional_edges(
    "model",
    should_continue,
    {"tool": "tool", END: END}
)

workflow.add_edge("tool", "model")

app_agent = workflow.compile()
logger.info("✅ Agent graph compiled and ready.")

class TaskAgent:
    def __init__(self):
        self.chat_history = []
    
    async def process_input(self, user_input: str):
        logger.info(f"🚦 Processing input: {user_input}")
        
        initial_state = {
            "input": user_input,
            "chat_history": self.chat_history.copy(),
            "tool_calls": [],
            "agent_outcome": None,
            "tasks_updated": False
        }
        
        result = await app_agent.ainvoke(initial_state)
        
        self.chat_history = result["chat_history"]
        
        logger.info(f"🧾 Processing complete. Chat history length: {len(self.chat_history)}")
        
        return result
    
    def clear_history(self):
        self.chat_history = []
        logger.info("🧹 Chat history cleared.")
    
    def get_final_response(self, result):
        if isinstance(result["agent_outcome"], str):
            return result["agent_outcome"]
        elif isinstance(result["agent_outcome"], list):
            responses = []
            for item in result["agent_outcome"]:
                if item["response"].get("status") == "success":
                    responses.append(item["response"].get("message", "Success"))
                else:
                    responses.append(item["response"].get("message", "Error"))
            return "\n".join(responses)
        else:
            return "Task completed successfully."

if __name__ == "__main__":
    import asyncio
    from datetime import datetime, timedelta

    async def run_agent():
        logger.info("🚦 Starting agent test run...")
        
        agent = TaskAgent()

        user_input_1 = "add a task to remind for gym tomorrow"
        logger.info("🧪 Test 1: Creating task")
        result_1 = await agent.process_input(user_input_1)
        print(f"Response 1: {agent.get_final_response(result_1)}")

        user_input_2 = "list all tasks"
        logger.info("🧪 Test 2: Listing tasks")
        result_2 = await agent.process_input(user_input_2)
        print(f"Response 2: {agent.get_final_response(result_2)}")

        user_input_3 = "add a task to pick up bag on 2nd aug 2025"
        logger.info("🧪 Test 3: Adding another task")
        result_3 = await agent.process_input(user_input_3)
        print(f"Response 3: {agent.get_final_response(result_3)}")

    asyncio.run(run_agent())