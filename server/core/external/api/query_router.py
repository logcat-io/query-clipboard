import os
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QuerySearchCriteria,
)
from server.core.application.dto.purpose_dto import CreatePurposeCommand
from server.core.application.usecase.query_usecase import QueryUseCase
from server.core.application.usecase.purpose_usecase import PurposeUseCase
from server.core.domain.exception.domain_exception import (
    QueryNotFoundException,
    InvalidQueryException,
    InvalidPurposeException,
)

templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates")
templates = Jinja2Templates(directory=os.path.abspath(templates_dir))


def create_query_router(use_case: QueryUseCase, purpose_use_case: PurposeUseCase) -> APIRouter:
    router = APIRouter()

    async def _render_context(
        request: Request,
        queries,
        current_purpose_id: Optional[int] = None,
        search_query: str = "",
        edit_query=None,
        error: str = None,
        status_code: int = 200,
    ):
        purposes = await purpose_use_case.get_all_purposes()

        ctx = {
            "request": request,
            "queries": queries,
            "purposes": purposes,
            "current_purpose_id": current_purpose_id,
            "search_query": search_query,
            "edit_query": edit_query,
        }
        if error:
            ctx["error"] = error
        return templates.TemplateResponse("index.html", ctx, status_code=status_code)

    @router.get("/")
    async def index(
        request: Request,
        purpose_id: Optional[int] = None,
        q: Optional[str] = None,
    ):
        criteria = QuerySearchCriteria(
            purpose_id=purpose_id,
            search=q if q else None,
        )

        if criteria.purpose_id or criteria.search:
            queries = await use_case.search_queries(criteria)
        else:
            queries = await use_case.get_all_queries()

        return await _render_context(
            request, queries,
            current_purpose_id=purpose_id,
            search_query=q or "",
        )

    @router.post("/add")
    async def add_query(
        request: Request,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose_id: int = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = CreateQueryCommand(
                title=title,
                description=description if description else None,
                purpose_id=purpose_id,
                tags=tags,
                sql_text=sql_text,
            )
            await use_case.create_query(command)
            return RedirectResponse(url="/", status_code=303)
        except InvalidQueryException as e:
            queries = await use_case.get_all_queries()
            return await _render_context(
                request, queries, error=e.message, status_code=400,
            )

    @router.get("/edit/{query_id}")
    async def edit_query_form(
        request: Request,
        query_id: int,
        purpose_id: Optional[int] = None,
        q: Optional[str] = None,
    ):
        try:
            edit_query = await use_case.get_query_by_id(query_id)

            criteria = QuerySearchCriteria(
                purpose_id=purpose_id,
                search=q if q else None,
            )
            if criteria.purpose_id or criteria.search:
                queries = await use_case.search_queries(criteria)
            else:
                queries = await use_case.get_all_queries()

            return await _render_context(
                request, queries,
                current_purpose_id=purpose_id,
                search_query=q or "",
                edit_query=edit_query,
            )
        except QueryNotFoundException:
            return RedirectResponse(url="/", status_code=303)

    @router.post("/edit/{query_id}")
    async def update_query(
        request: Request,
        query_id: int,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose_id: int = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = UpdateQueryCommand(
                title=title,
                description=description if description else None,
                purpose_id=purpose_id,
                tags=tags,
                sql_text=sql_text,
            )
            await use_case.update_query(query_id, command)
            return RedirectResponse(url="/", status_code=303)
        except QueryNotFoundException:
            return RedirectResponse(url="/", status_code=303)
        except InvalidQueryException as e:
            queries = await use_case.get_all_queries()
            edit_query = None
            try:
                edit_query = await use_case.get_query_by_id(query_id)
            except QueryNotFoundException:
                pass
            return await _render_context(
                request, queries,
                edit_query=edit_query,
                error=e.message,
                status_code=400,
            )

    @router.post("/delete/{query_id}")
    async def delete_query(query_id: int):
        try:
            await use_case.delete_query(query_id)
        except QueryNotFoundException:
            pass
        return RedirectResponse(url="/", status_code=303)

    @router.post("/purposes/add")
    async def add_purpose(name: str = Form(...), sort_order: int = Form(0)):
        try:
            command = CreatePurposeCommand(name=name, sort_order=sort_order)
            await purpose_use_case.create_purpose(command)
        except InvalidPurposeException:
            pass
        return RedirectResponse(url="/", status_code=303)

    @router.post("/purposes/delete/{purpose_id}")
    async def delete_purpose(purpose_id: int):
        try:
            await purpose_use_case.delete_purpose(purpose_id)
        except InvalidPurposeException:
            pass
        return RedirectResponse(url="/", status_code=303)

    return router
