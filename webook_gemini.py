import functions_framework
import google.cloud.logging
import sys
import logging
import vertexai
from vertexai.preview.generative_models import (
    GenerationResponse,
    GenerativeModel,
    GenerationConfig,
    Tool,
    grounding,
    Part,
    Content,
    SafetySetting
)

from vertexai.preview.generative_models.grounding import grounding as grd

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
PROJECT_ID = "your-project-id"
LOCATION = "LOCATION"
vertexai.init(project=PROJECT_ID, location=LOCATION)

model = GenerativeModel.from_pretrained("gemini-pro", system_instructions="You are a helpful assistant.")

#Grounding
DATA_STORE_PROJECT_ID = "your-datastore-project-id"
DATA_STORE_REGION = "region"
DATA_STORE_ID = "your-datastore-id"

@functions_framework.http
def main(request):
    try:
        request_json = request.get_json(silent=True)
        session_info = request_json.get("sessionInfo")
        para = session_info.get('parameters')

        """ logic to handle the webhook request """

        generation_config = GenerationConfig(
            max_output_tokens=1024,
            temperature=0.2,
            top_p=0.8,
            max_output=40,
        )

        safety_settings=[
            SafetySetting(
                category="HATE_SPEECH",
                threshold="BLOCK_ONLY"
            ),
            SafetySetting(
                category="SEXUALLY_EXPLICIT",
                threshold="BLOCK_ONLY"
            ),
            SafetySetting(
                category="DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY"
            )
        ]

        tool = Tool.from_retrieval(
            grd.Retrieval(
                grd.VertexAISearch(
                    project_id=DATA_STORE_PROJECT_ID,
                    region=DATA_STORE_REGION,
                    datastore_id=DATA_STORE_ID,
                )
            )
        )

        response = model.generate_content(
            prompt=para.get("user_query"),  ## Handled above in the webhook request
            generation_config=generation_config,
            tools=[tool],
            safety_settings=safety_settings
        )

        text_string = response if response.text is not None else "No response"
        logging.info(f"Response: {text_string[:100]}") # Log first 100 characters of the response

        res = {
            "fulfill_response": {
                "messages": [
                    {
                        "text": {
                            "text": [text_string]
                        }
                    }
                ]
            }
        }

        return res
    except Exception as e:
        logging.exception(f"Error processing the request: {e}")
        return {"fullfill_response": {"messages": [{"text": {"text": ["An error occurred while processing your request."]}}]}}
    
