import logging
from typing import Union

from moonshot.src.connectors.connector import Connector, perform_retry
from moonshot.src.connectors.connector_response import ConnectorResponse
from moonshot.src.connectors_endpoints.connector_endpoint_arguments import (
    ConnectorEndpointArguments,
)
from openai import AsyncAzureOpenAI, BadRequestError
from openai.types import ImagesResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AzureOpenAIT2IConnector(Connector):
    def __init__(self, ep_arguments: ConnectorEndpointArguments):
        # Initialize super class
        super().__init__(ep_arguments)

        # Azure OpenAI has additional parameters
        self.api_version = self.optional_params.get("api_version", "2024-02-01")

        # Set OpenAI Key
        self._client = AsyncAzureOpenAI(
            api_key=self.token,
            # https://learn.microsoft.com/azure/ai-services/openai/reference#rest-api-versioning
            api_version=self.api_version,
            # https://learn.microsoft.com/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource
            azure_endpoint=self.endpoint,
        )

        # Set the model to use and remove it from optional_params if it exists
        self.model = self.optional_params.get("model", "")

    @Connector.rate_limited
    @perform_retry
    async def get_response(self, prompt: str) -> ConnectorResponse:
        """
        Asynchronously sends a prompt to the Azure OpenAI API and returns the generated response.

        This method constructs a request with the given prompt, optionally prepended and appended with
        predefined strings, and sends it to the Azure OpenAI API. If a system prompt is set, it is included in the
        request. The method then awaits the response from the API, processes it, and returns the resulting image
        content as a base64-encoded string or a list of base64-encoded strings.

        Args:
            prompt (str): The input prompt to send to the Azure OpenAI API.

        Returns:
            ConnectorResponse: An object containing the base64-encoded image(s) generated by the Azure OpenAI model.
        """
        connector_prompt = f"{self.pre_prompt}{prompt}{self.post_prompt}"

        # Merge self.optional_params with additional parameters
        new_params = {
            **self.optional_params,
            "model": self.model,
            "prompt": connector_prompt,
            "timeout": self.timeout,
            "response_format": "b64_json",
        }
        blackout = (
            "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAADEUlEQVR4nO3BgQAAAADDoPl"
            "TX+EAVQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMBvArQAAVkUTe8AAAAASUVORK5CYII="
        )
        try:
            response = await self._client.images.generate(**new_params)
            logging.debug(f"[AzureOpenAIT2IConnector] {'*'*5} No Blackout {'*'*5}")
            return ConnectorResponse(
                response=await self._process_response(response, prompt)
            )
        except BadRequestError:
            logging.warning(f"[AzureOpenAIT2IConnector] {'*'*5} Blackout {'*'*5}")
            return ConnectorResponse(response=blackout)
        except Exception as e:
            logging.error(f"[AzureOpenAIT2IConnector] Failed to get response: {e}")
            raise

    async def _process_response(
        self, response: ImagesResponse, prompt: str
    ) -> Union[str, list[str]]:
        """
        Process the response from OpenAI's API and return the image content as a base64-encoded string or
        list of strings.

        This method processes the response received from OpenAI's API call, specifically targeting
        the image generation response structure. It extracts the base64-encoded image content from the response.

        Args:
            response (ImagesResponse): The response object received from an OpenAI API call. It is expected to
            follow the structure of OpenAI's image generation response.
            prompt (str): The input prompt that was sent to the OpenAI API.

        Returns:
            Union[str, list[str]]: A base64-encoded string if there is only one image, otherwise a
            list of base64-encoded strings.
        """
        try:
            encoded_strings = []
            for image in response.data:
                encoded_strings.append(image.b64_json)
            # Return a single string if there is only one image, otherwise return the list of encoded strings
            return encoded_strings[0] if len(encoded_strings) == 1 else encoded_strings

        except Exception as e:
            logging.error(f"Error processing response: {e}")
            raise
