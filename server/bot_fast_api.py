import os
import sys
import asyncio
from dotenv import load_dotenv
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.services.gemini_multimodal_live.gemini import (
    GeminiMultimodalLiveLLMService,
    InputParams,
    GeminiMultimodalModalities,
)

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

SYSTEM_INSTRUCTION = """
Hamza gandu Hello
"""

async def run_bot(websocket_client):
    
    async def hangup_call(params: FunctionCallParams):
        logger.info("🔔 Hangup tool called — ending the session.")
        try:
            await websocket_client.close()
            logger.success("✅ Session closed successfully via hangup_call.")
            await params.result_callback({})
        except Exception as e:
            logger.exception(f"❌ Exception in hangup_call: {e}")

    TOOLS = [
        {
            "function_declarations": [
                {
                    "name": "hangup_call",
                    "description": "Politely end the current call when conversation has ended.",
                },
            ]
        }
    ]

    ws_transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=ProtobufFrameSerializer(),
        ),
    )

    llm = GeminiMultimodalLiveLLMService(
        api_key="AIzaSyDD9XA-J5KC5IowbYkjLeD-LRAkLdxduQA",
        voice_id="Aoede",  # Aoede, Charon, Fenrir, Kore, Puck
        transcribe_model_audio=True,
        transcribe_user_audio=True,
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        params=InputParams(
            temperature=0.7,  # Set model input params
            modalities=GeminiMultimodalModalities.AUDIO,  # Response modality
        ),
    )

    llm.register_function("hangup_call", hangup_call)

    context = OpenAILLMContext(
        [
            {
                "role": "user",
                "content": "Start by greeting the user warmly and introducing yourself.",
            }
        ],
    )
    context_aggregator = llm.create_context_aggregator(context)

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    pipeline = Pipeline(
        [
            ws_transport.input(),
            context_aggregator.user(),
            rtvi,
            llm,
            ws_transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    @rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("Pipecat client ready.")
        await rtvi.set_bot_ready()
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @ws_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")

    @ws_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Conversation ended. Full history:")
        for msg in context.messages:
            role = msg.get("role", "UNKNOWN").upper()
            content = msg.get("content", "<No content>")
            logger.info(f"  {role}: {content!r}")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)
