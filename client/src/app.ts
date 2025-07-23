import {
    RTVIClient,
    RTVIClientOptions,
    RTVIEvent,
} from "@pipecat-ai/client-js";
import { WebSocketTransport } from "@pipecat-ai/websocket-transport";

class WebsocketClientApp {
    private rtviClient: RTVIClient | null = null;
    private connectBtns: NodeListOf<HTMLButtonElement> | null = null;
    private disconnectBtn: HTMLButtonElement | null = null;
    private statusSpan: HTMLElement | null = null;
    private debugLog: HTMLElement | null = null;
    private botAudio: HTMLAudioElement;

    constructor() {
        console.log("WebsocketClientApp");
        this.botAudio = document.createElement("audio");
        this.botAudio.autoplay = true;
        document.body.appendChild(this.botAudio);

        this.setupDOMElements();
        this.setupEventListeners();
    }

    private setupDOMElements(): void {
        this.connectBtns = document.querySelectorAll(
            ".connect-btn"
        ) as NodeListOf<HTMLButtonElement>;
        this.disconnectBtn = document.getElementById(
            "disconnect-btn"
        ) as HTMLButtonElement;
        this.statusSpan = document.getElementById("connection-status");
        this.debugLog = document.getElementById("debug-log");
    }

    private setupEventListeners(): void {
        this.connectBtns?.forEach(button => {
            button.addEventListener("click", () => {
                const promptType = button.dataset.prompt;
                if (promptType) {
                    this.connect(promptType);
                }
            });
        });
        this.disconnectBtn?.addEventListener("click", () => this.disconnect());
    }

    private log(message: string): void {
        if (!this.debugLog) return;
        const entry = document.createElement("div");
        entry.textContent = `${new Date().toISOString()} - ${message}`;
        if (message.startsWith("User: ")) {
            entry.style.color = "#2196F3";
        } else if (message.startsWith("Bot: ")) {
            entry.style.color = "#4CAF50";
        }
        this.debugLog.appendChild(entry);
        this.debugLog.scrollTop = this.debugLog.scrollHeight;
        console.log(message);
    }

    private updateStatus(status: string): void {
        if (this.statusSpan) {
            this.statusSpan.textContent = status;
        }
        this.log(`Status: ${status}`);
    }

    setupMediaTracks() {
        if (!this.rtviClient) return;
        const tracks = this.rtviClient.tracks();
        if (tracks.bot?.audio) {
            this.setupAudioTrack(tracks.bot.audio);
        }
    }

    setupTrackListeners() {
        if (!this.rtviClient) return;

        this.rtviClient.on(RTVIEvent.TrackStarted, (track, participant) => {
            if (!participant?.local && track.kind === "audio") {
                this.setupAudioTrack(track);
            }
        });

        this.rtviClient.on(RTVIEvent.TrackStopped, (track, participant) => {
            this.log(
                `Track stopped: ${track.kind} from ${participant?.name || "unknown"}`
            );
        });
    }

    /**
     * Set up an audio track for playback
     * Handles both initial setup and track updates
     */
    private setupAudioTrack(track: MediaStreamTrack): void {
        this.log("Setting up audio track");
        if (
            this.botAudio.srcObject &&
            "getAudioTracks" in this.botAudio.srcObject
        ) {
            const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
            if (oldTrack?.id === track.id) return;
        }
        this.botAudio.srcObject = new MediaStream([track]);
    }

    /**
     * Initialize and connect to the bot
     * This sets up the RTVI client, initializes devices, and establishes the connection
     */
    public async connect(promptType: string): Promise<void> {
        try {
            const startTime = Date.now();

            const transport = new WebSocketTransport();
            const RTVIConfig: RTVIClientOptions = {
                transport,
                params: {
                    // Explicitly setting the backend Heroku URL
                    // This URL should use HTTPS for the initial POST /connect request
                    baseUrl: "https://ths-pipecat-server-742812f8a26b.herokuapp.com",
                    endpoints: { connect: `/connect?prompt_type=${promptType}` },
                },
                enableMic: true,
                enableCam: false,
                callbacks: {
                    onConnected: () => {
                        this.updateStatus(`Connected (${promptType})`);
                        this.connectBtns?.forEach(btn => btn.disabled = true);
                        if (this.disconnectBtn) this.disconnectBtn.disabled = false;
                    },
                    onDisconnected: () => {
                        this.updateStatus("Disconnected");
                        this.connectBtns?.forEach(btn => btn.disabled = false);
                        if (this.disconnectBtn) this.disconnectBtn.disabled = true;
                        this.log("Client disconnected");
                    },
                    onBotReady: (data) => {
                        this.log(`Bot ready: ${JSON.stringify(data)}`);
                        this.setupMediaTracks();
                    },
                    onUserTranscript: (data) => {
                        if (data.final) {
                            this.log(`User: ${data.text}`);
                        }
                    },
                    onBotTranscript: (data) => this.log(`Bot: ${data.text}`),
                    onMessageError: (error) => console.error("Message error:", error),
                    onError: (error) => console.error("Error:", error),
                },
            };
            this.rtviClient = new RTVIClient(RTVIConfig);
            this.setupTrackListeners();

            this.log("Initializing devices...");
            await this.rtviClient.initDevices();

            this.log(`Connecting to bot with prompt_type=${promptType}...`);
            await this.rtviClient.connect();

            const timeTaken = Date.now() - startTime;
            this.log(`Connection complete, timeTaken: ${timeTaken}`);
        } catch (error) {
            this.log(`Error connecting: ${(error as Error).message}`);
            this.updateStatus("Error");
            // Clean up if there's an error and client was initialized
            if (this.rtviClient) {
                try {
                    await this.rtviClient.disconnect();
                } catch (disconnectError) {
                    this.log(`Error during disconnect: ${disconnectError}`);
                }
            }
        }
    }

    /**
     * Disconnect from the bot and clean up media resources
     */
    public async disconnect(): Promise<void> {
        if (this.rtviClient) {
            try {
                await this.rtviClient.disconnect();
                this.rtviClient = null;
                if (
                    this.botAudio.srcObject &&
                    "getAudioTracks" in this.botAudio.srcObject
                ) {
                    this.botAudio.srcObject
                        .getAudioTracks()
                        .forEach((track) => track.stop());
                    this.botAudio.srcObject = null;
                }
            } catch (error) {
                this.log(`Error disconnecting: ${(error as Error).message}`);
            }
        }
    }
}

declare global {
    interface Window {
        WebsocketClientApp: typeof WebsocketClientApp;
    }
}

window.addEventListener("DOMContentLoaded", () => {
    window.WebsocketClientApp = WebsocketClientApp;
    new WebsocketClientApp();
});