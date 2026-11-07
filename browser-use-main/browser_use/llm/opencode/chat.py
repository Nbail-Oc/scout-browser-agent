import json
import logging
import re
from dataclasses import dataclass
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel, ValidationError

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```', re.IGNORECASE)


def _unwrap_json_content(content: str) -> str:
	"""Strip markdown code fences from JSON output if present."""
	text = content.strip()
	match = _JSON_FENCE_RE.search(text)
	if match:
		return match.group(1).strip()
	return text


@dataclass
class ChatOpenCode(BaseChatModel):
	"""
	A wrapper around the headless OpenCode daemon service (:4096).
	"""

	model: str = 'opencode/deepseek-v4-flash-free'
	base_url: str = 'http://127.0.0.1:4096'
	timeout: float = 120.0
	session_id: str | None = None

	@property
	def provider(self) -> str:
		return 'opencode'

	@property
	def name(self) -> str:
		return f'OpenCode-{self.model}'

	async def _get_or_create_session(self, client: httpx.AsyncClient) -> str:
		if self.session_id:
			return self.session_id

		try:
			res = await client.post(
				f'{self.base_url.rstrip("/")}/session',
				json={'title': f'browser-use-{self.model}'},
			)
			res.raise_for_status()
			data = res.json()
			self.session_id = data.get('id') or data.get('sessionID')
			if not self.session_id:
				raise ModelProviderError('OpenCode session creation failed: no session ID in response')
			return self.session_id
		except Exception as e:
			raise ModelProviderError(f'Failed to connect to OpenCode server at {self.base_url}: {e}') from e

	def _format_messages_for_prompt(self, messages: list[BaseMessage], output_format: type[T] | None = None) -> str:
		prompt_parts = []
		for msg in messages:
			role = getattr(msg, 'role', 'user')
			content = getattr(msg, 'content', '')
			if isinstance(content, list):
				text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
				content_str = ' '.join(text_parts)
			else:
				content_str = str(content)
			prompt_parts.append(f'[{role.upper()}]:\n{content_str}')

		full_prompt = '\n\n'.join(prompt_parts)

		if output_format is not None:
			schema_json = json.dumps(output_format.model_json_schema(), indent=2)
			full_prompt += (
				'\n\n[INSTRUCTION]:\n'
				'You must output ONLY a valid JSON object matching the JSON schema below. '
				'Do not include any explanation or extra text outside the JSON object.\n\n'
				f'JSON Schema:\n{schema_json}'
			)

		return full_prompt

	@overload
	async def ainvoke(
		self, messages: list[BaseMessage], output_format: None = None, **kwargs: Any
	) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T], **kwargs: Any) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs: Any
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		prompt_text = self._format_messages_for_prompt(messages, output_format)

		async with httpx.AsyncClient(timeout=self.timeout) as client:
			session_id = await self._get_or_create_session(client)

			payload = {
				'parts': [{'type': 'text', 'text': prompt_text}],
			}

			try:
				res = await client.post(
					f'{self.base_url.rstrip("/")}/session/{session_id}/message',
					json=payload,
				)
				res.raise_for_status()
				data = res.json()
			except Exception as e:
				raise ModelProviderError(f'Error communicating with OpenCode daemon: {e}') from e

			# Extract message text from OpenCode response parts
			content_text = ''
			if isinstance(data, dict):
				if 'parts' in data and isinstance(data['parts'], list):
					for part in data['parts']:
						if isinstance(part, dict) and part.get('type') == 'text':
							content_text += part.get('text', '')
				elif 'text' in data:
					content_text = str(data['text'])
				elif 'content' in data:
					content_text = str(data['content'])
				else:
					content_text = json.dumps(data)
			else:
				content_text = str(data)

			raw_output = _unwrap_json_content(content_text)

			if output_format is not None:
				try:
					parsed_obj = output_format.model_validate_json(raw_output)
					return ChatInvokeCompletion(
						completion=parsed_obj,
						usage=ChatInvokeUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
					)
				except ValidationError as val_err:
					logger.error(f'OpenCode JSON validation error: {val_err}\nRaw output was: {raw_output}')
					# Try loose JSON parse before giving up
					try:
						loose_dict = json.loads(raw_output)
						parsed_obj = output_format.model_validate(loose_dict)
						return ChatInvokeCompletion(
							completion=parsed_obj,
							usage=ChatInvokeUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
						)
					except Exception:
						raise ModelProviderError(f'Failed to parse OpenCode response into {output_format.__name__}: {val_err}') from val_err

			return ChatInvokeCompletion(
				completion=content_text,
				usage=ChatInvokeUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
			)
