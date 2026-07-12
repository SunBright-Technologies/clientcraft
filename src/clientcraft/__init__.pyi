from collections.abc import Coroutine
from typing import Any, overload

from pydantic import BaseModel

from ._base import DomainError as DomainError
from ._base import ErrorMap as ErrorMap
from ._base import HttpError as HttpError
from ._base import PreparedRequest as PreparedRequest
from ._base import prepare_request as prepare_request
from ._responses import BytesResponse as BytesResponse
from ._responses import TextResponse as TextResponse
from ._types import EndpointInfo as EndpointInfo
from ._types import ExtractedEndpoint as ExtractedEndpoint
from ._types import Raises as Raises
from ._types import RequestStyle as RequestStyle
from ._types import ResponseStyle as ResponseStyle
from .async_client import AsyncAPIClient as AsyncAPIClient
from .backends import AsyncHttpBackend as AsyncHttpBackend
from .backends import HttpBackend as HttpBackend
from .backends import HttpResponse as HttpResponse
from .client import APIClient as APIClient

# Metaclass exposing runtime subscription: at runtime ``Get[Req, Resp, Path]`` is
# evaluated by ``_EndpointTypeMeta.__getitem__`` and returns an ``Annotated`` type.
# Declaring it on the base classes (subclasses inherit it) lets a value of type
# ``type[Get]`` be used as a subscriptable factory (e.g. in tests) without losing
# static typing on the generic-class annotation form.
class _EndpointTypeMeta(type):
    def __getitem__(cls, params: tuple[type | None, type | None, object]) -> object: ...

class Endpoint[TRequest: BaseModel | None, TResponse: BaseModel | None](metaclass=_EndpointTypeMeta):
    # When TRequest is None the endpoint takes no parameters: it may be called with
    # no argument or with an explicit None. Otherwise the request is required.
    @overload
    def __call__(self: Endpoint[None, TResponse], request: None = ...) -> TResponse: ...
    @overload
    def __call__(self, request: TRequest) -> TResponse: ...

class Get[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](Endpoint[TRequest, TResponse]): ...
class Post[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](Endpoint[TRequest, TResponse]): ...
class Put[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](Endpoint[TRequest, TResponse]): ...
class Patch[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](Endpoint[TRequest, TResponse]): ...
class Delete[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](Endpoint[TRequest, TResponse]): ...

class AsyncEndpoint[TRequest: BaseModel | None, TResponse: BaseModel | None](metaclass=_EndpointTypeMeta):
    @overload
    def __call__(self: AsyncEndpoint[None, TResponse], request: None = ...) -> Coroutine[Any, Any, TResponse]: ...
    @overload
    def __call__(self, request: TRequest) -> Coroutine[Any, Any, TResponse]: ...

class AsyncGet[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](
    AsyncEndpoint[TRequest, TResponse]
): ...
class AsyncPost[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](
    AsyncEndpoint[TRequest, TResponse]
): ...
class AsyncPut[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](
    AsyncEndpoint[TRequest, TResponse]
): ...
class AsyncPatch[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](
    AsyncEndpoint[TRequest, TResponse]
): ...
class AsyncDelete[TRequest: BaseModel | None, TResponse: BaseModel | None, TPath: str](
    AsyncEndpoint[TRequest, TResponse]
): ...

def extract_endpoint_info(hint: object) -> ExtractedEndpoint | None: ...
