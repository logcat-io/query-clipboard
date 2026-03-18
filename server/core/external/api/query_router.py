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
from server.core.application.usecase.query_usecase import QueryUseCase
from server.core.domain.exception.domain_exception import (
    QueryNotFoundException,
    InvalidQueryException,
)

PURPOSES = ["조회", "수정", "삭제", "집계", "기타"]

templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates")
templates = Jinja2Templates(directory=os.path.abspath(templates_dir))


def create_query_router(use_case: QueryUseCase) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def index(
        request: Request,
        purpose: Optional[str] = None,
        q: Optional[str] = None,
    ):
        criteria = QuerySearchCriteria(
            purpose=purpose if purpose else None,
            search=q if q else None,
        )

        if criteria.purpose or criteria.search:
            queries = await use_case.search_queries(criteria)
        else:
            queries = await use_case.get_all_queries()

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "queries": queries,
                "purposes": PURPOSES,
                "current_purpose": purpose or "",
                "search_query": q or "",
                "edit_query": None,
            },
        )

    @router.post("/add")
    async def add_query(
        request: Request,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose: str = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = CreateQueryCommand(
                title=title,
                description=description if description else None,
                purpose=purpose,
                tags=tags,
                sql_text=sql_text,
            )
            await use_case.create_query(command)
            return RedirectResponse(url="/", status_code=303)
        except InvalidQueryException as e:
            queries = await use_case.get_all_queries()
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": "",
                    "search_query": "",
                    "edit_query": None,
                    "error": e.message,
                },
                status_code=400,
            )

    @router.get("/edit/{query_id}")
    async def edit_query_form(
        request: Request,
        query_id: int,
        purpose: Optional[str] = None,
        q: Optional[str] = None,
    ):
        try:
            edit_query = await use_case.get_query_by_id(query_id)

            criteria = QuerySearchCriteria(
                purpose=purpose if purpose else None,
                search=q if q else None,
            )
            if criteria.purpose or criteria.search:
                queries = await use_case.search_queries(criteria)
            else:
                queries = await use_case.get_all_queries()

            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": purpose or "",
                    "search_query": q or "",
                    "edit_query": edit_query,
                },
            )
        except QueryNotFoundException:
            return RedirectResponse(url="/", status_code=303)

    @router.post("/edit/{query_id}")
    async def update_query(
        request: Request,
        query_id: int,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose: str = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = UpdateQueryCommand(
                title=title,
                description=description if description else None,
                purpose=purpose,
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
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": "",
                    "search_query": "",
                    "edit_query": edit_query,
                    "error": e.message,
                },
                status_code=400,
            )

    @router.post("/delete/{query_id}")
    async def delete_query(query_id: int):
        try:
            await use_case.delete_query(query_id)
        except QueryNotFoundException:
            pass
        return RedirectResponse(url="/", status_code=303)

    return router
