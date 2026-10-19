"""Builds config.json (the ElevenAgents create payload) from prompt.md + the settings below.

Run: python3 scripts/build_config.py
The prompt lives in prompt.md so it can be reviewed as a document; config.json is generated.
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIRST_MESSAGE = (
    "¡Hola! Soy Sol, la asistente virtual de Tiendalia. "
    "Te acompaño a dejar tu tienda lista para vender. "
    "¿Arrancamos viendo en qué paso estás?"
)


def system_tool(name, description):
    return {
        "type": "system",
        "name": name,
        "description": description,
        "params": {"system_tool_type": name},
    }


def build():
    with open(os.path.join(HERE, "prompt.md"), encoding="utf-8") as f:
        prompt = f.read().strip() + "\n"
    config = {
        "name": "Demo - Sol, onboarding de Tiendalia (rioplatense)",
        "tags": ["demo", "onboarding", "es-AR"],
        "conversation_config": {
            "agent": {
                "first_message": FIRST_MESSAGE,
                "language": "es",
                "max_conversation_duration_message": (
                    "Se nos está terminando el tiempo de esta llamada. "
                    "Te dejo anotado el próximo paso y cuando quieras seguimos."
                ),
                "silence_end_call_message": (
                    "Parece que se cortó o estás ocupada. Te dejo seguir; cuando quieras, me volvés a llamar."
                ),
                "prompt": {
                    "prompt": prompt,
                    "llm": "gpt-6-luna",
                    "temperature": 0.3,
                    "built_in_tools": {
                        "end_call": system_tool(
                            "end_call",
                            "Termina la llamada cuando la persona se despide o ya quedó claro el próximo paso.",
                        ),
                        "skip_turn": system_tool(
                            "skip_turn",
                            "Se queda en silencio mientras la persona hace un paso en el panel.",
                        ),
                    },
                },
            },
            "tts": {
                "model_id": "eleven_flash_v2_5",
                "voice_id": "bN1bDXgDIGX5lw0rtY2B",
                "stability": 0.55,
                "similarity_boost": 0.75,
                "speed": 1.0,
            },
            "asr": {"keywords": ["Tiendalia", "productos", "envíos", "medios de cobro"]},
            "turn": {
                "turn_timeout": 7.0,
                "silence_end_call_timeout": 45.0,
                "soft_timeout_config": {
                    "timeout_seconds": 3.0,
                    "message": "Dame un segundito…",
                },
            },
            "conversation": {"max_duration_seconds": 600},
        },
        "platform_settings": {
            "evaluation": {
                "criteria": [
                    {
                        "id": "paso_completado",
                        "name": "Paso de activación completado",
                        "conversation_goal_prompt": (
                            "¿La persona completó durante la llamada al menos uno de los cuatro pasos de activación "
                            "(cargar tres productos, configurar cobro, configurar envío o publicar la tienda)?"
                        ),
                    },
                    {
                        "id": "proximo_paso_claro",
                        "name": "Próximo paso claro al cierre",
                        "conversation_goal_prompt": (
                            "¿La agente terminó la llamada nombrando un único próximo paso pendiente, concreto?"
                        ),
                    },
                    {
                        "id": "sin_informacion_inventada",
                        "name": "Sin información inventada",
                        "conversation_goal_prompt": (
                            "¿La agente evitó inventar funciones, precios, plazos o políticas que no están en sus "
                            "instrucciones, y dijo que no sabía cuando correspondía?"
                        ),
                    },
                    {
                        "id": "derivacion_correcta",
                        "name": "Derivación correcta",
                        "conversation_goal_prompt": (
                            "Si la persona preguntó por facturación, su cuenta, un pago o pidió una persona, ¿la agente "
                            "derivó al chat de Ayuda explicando dónde está y el horario? Si no hubo motivo de derivación, "
                            "marcá éxito."
                        ),
                    },
                    {
                        "id": "sin_datos_sensibles",
                        "name": "No pidió datos sensibles",
                        "conversation_goal_prompt": (
                            "¿La agente evitó pedir o repetir contraseñas, códigos, números de tarjeta, CBU, CVU o DNI?"
                        ),
                    },
                ]
            },
            "data_collection": {
                "etapa_onboarding": {
                    "type": "string",
                    "enum": [
                        "sin_productos",
                        "productos_cargados",
                        "cobros_configurados",
                        "envios_configurados",
                        "tienda_publicada",
                    ],
                    "description": "Último paso de activación completo al terminar la llamada.",
                },
                "pasos_completados_en_llamada": {
                    "type": "integer",
                    "description": "Cuántos de los cuatro pasos completó la persona durante esta llamada (0 a 4).",
                },
                "bloqueo_principal": {
                    "type": "string",
                    "description": (
                        "En pocas palabras, qué frenó a la persona (por ejemplo: fotos, precios, cobro, envío). "
                        "Vacío si no hubo bloqueo. Sin datos personales."
                    ),
                },
                "derivada_a_soporte": {
                    "type": "boolean",
                    "description": "Verdadero si la agente derivó al chat de Ayuda.",
                },
            },
            "guardrails": {
                "version": "1",
                "focus": {"is_enabled": True},
                "prompt_injection": {"is_enabled": True},
            },
            "privacy": {"retention_days": 30, "record_voice": True},
            "call_limits": {"agent_concurrency_limit": 2, "daily_limit": 50},
        },
    }
    out = os.path.join(HERE, "config.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote", out)


if __name__ == "__main__":
    build()
