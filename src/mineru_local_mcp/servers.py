#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : servers.py

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .client import MineruLocalClient, MineruWebClient


mineru_mcp = FastMCP(
    name="mineru-mcp"
)


def _web_process(file_path: str, save_to: Path = None) -> bool:
    client = MineruWebClient(save_to=save_to)
    task_id = client.create_task(file_path).get("data", {}).get("task_id")
    status = client.save_result(task_id=task_id)
    return status


def _local_process(file_path: str, save_to: Path = None) -> bool:
    client = MineruLocalClient(save_to=save_to)
    return client.process(file_path).get("success", False)


@mineru_mcp.tool(
    name="process",
    description="Process a PDF file to a set of markdown file"
)
def process(file_path: str, save_to: Path = None) -> bool:
    """
    MinerU Process.

    Args:
        file_path: the file which will be processed path.
        save_to: save to path, default is cwd/mineru_results/file_name

    Returns:
        bool: status of process
    """
    _client = os.getenv("MINERU_CLIENT", "local")

    if not save_to:
        save_to = Path.cwd() / "mineru_results"

    if _client == "local":
        return _local_process(file_path, save_to)
    else:
        return _web_process(file_path, save_to)


if __name__ == "__main__":
    mineru_mcp.run()
