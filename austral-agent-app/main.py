import asyncio
from bedrock_agentcore import BedrockAgentCoreApp
from orchestrator import PrincipalSupervisor

# Initialize the AgentCore App
app = BedrockAgentCoreApp()
supervisor = PrincipalSupervisor()

@app.entrypoint
async def invoke(payload):
    """
    Standard AgentCore Entry Point.
    Payload: {"prompt": "Analyze my solar for tomorrow"}
    """
    user_prompt = payload.get("prompt", "")
    
    # Run the agentic workflow
    result = await supervisor.route_and_execute(user_prompt)
    
    return {
        "status": "SUCCESS",
        "output_text": result["summary"],
        "plotly_data": result["visual"]
    }

if __name__ == "__main__":
    # Local testing entry
    app.run()