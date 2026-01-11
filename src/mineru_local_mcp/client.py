#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : client.py

import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict

import requests
from mineru.cli.common import do_parse
from mineru.utils.config_reader import get_device


class MineruLocalClient:
    def __init__(self,
                 save_to: Path = None,
                 *,
                 backend: str = "vlm-auto-engine",
                 vram: int = 12,
                 source: str = "huggingface"):
        """
        Initialize MinerU local client

        Args:
            save_to: Directory to save processed results
            backend: Parser backend (pipeline, vlm-auto-engine, hybrid-auto-engine, etc.)
            vram: GPU memory limit in GB
            source: Model source (huggingface, modelscope, local)
        """
        self.save_to = save_to or Path.home() / "mineru-mcp-storage"
        self.save_to.mkdir(parents=True, exist_ok=True)

        self.backend = backend
        self.vram = vram
        self.source = source

        # 设置环境变量
        if os.getenv('MINERU_DEVICE_MODE', None) is None:
            os.environ['MINERU_DEVICE_MODE'] = get_device()

        if os.getenv('MINERU_VIRTUAL_VRAM_SIZE', None) is None:
            os.environ['MINERU_VIRTUAL_VRAM_SIZE'] = str(self.vram)

        if os.getenv('MINERU_MODEL_SOURCE', None) is None:
            os.environ['MINERU_MODEL_SOURCE'] = self.source

    def process(self,
                file_path: str | Path,
                lang: str = "ch") -> Dict:
        """
        Process a single file with MinerU

        Args:
            file_path: Path to the file (PDF)
            lang: Language code for OCR (ch, en, etc.)

        Returns:
            Dict with processing result status
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        try:
            # 读取文件字节数据
            pdf_bytes = file_path.read_bytes()
            file_name = file_path.stem

            # 调用do_parse进行解析
            do_parse(
                output_dir=self.save_to.as_posix(),
                pdf_file_names=[file_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=[lang],
                backend=self.backend,
                parse_method="auto",
                formula_enable=True,
                table_enable=True,
            )

            return {
                "success": True,
                "output_dir": str(self.save_to / file_name),
                "message": f"Successfully processed {file_path.name}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class MineruWebClient:
    def __init__(self,
                 token: str = None,
                 base_url: str = None,
                 save_to: Path = None):
        self.token = token or os.getenv("MINERU_TOKEN")
        self.base_url = base_url or "https://mineru.net/api/v4/extract/task"
        self.base_url.strip("/")

        self.save_to = save_to or Path.home() / "mineru-mcp-storage"
        self.save_to.mkdir(parents=True, exist_ok=True)

        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def create_task(self,
                    file_path,
                    data_id: str = None,
                    model_version: str = "vlm",
                    lang: str = "ch") -> Dict:
        """
        Create a MinerU task.

        Args:
            file_path: file url.
            data_id: identification of file path
            model_version: mineru backend, ["pipeline", "vlm"]
            lang: language of file, default is 'ch'. ["ch", "en", "fr", ...]

        Returns:
            Dict: MinerU post requests response.

        Notes:
            language options: https://www.paddleocr.ai/latest/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html#_3
        """
        if not data_id:
            file_pure_name = file_path.split("/")[-1]
            data_id = file_pure_name.split(".")[0]
        res = requests.post(
            self.base_url,
            headers=self.header,
            json={
                "url": file_path,
                "data_id": data_id,
                "model_version": model_version,
                "language": lang,
            }
        )
        return res.json()

    def get_task_status(self, task_id: str) -> Dict:
        url = f"{self.base_url}/{task_id}"
        res = requests.get(url, headers=self.header)
        return res.json()

    def save_result(self,
                    task_id: str,
                    data_id: str = None,
                    save_to: Path = None) -> bool:
        result = self.get_task_status(task_id)
        full_zip_url = result.get("data", {}).get("full_zip_url")
        if not full_zip_url:
            return False
        data_id = data_id or task_id
        # 设置保存目录
        save_to = save_to or self.save_to
        # 在save_to下创建data_id子目录
        actual_save_to = save_to / data_id
        actual_save_to.mkdir(parents=True, exist_ok=True)

        # 创建临时目录和临时zip文件路径
        tmp_dir = Path.home() / "tmp" / f"mineru_{task_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_zip_file = tmp_dir / f"{task_id}.zip"

        try:
            # 下载zip文件
            print(f"Downloading from {full_zip_url}...")
            res = requests.get(full_zip_url, stream=True)
            res.raise_for_status()

            total_size = int(res.headers.get('content-length', 0))
            downloaded_size = 0

            with open(tmp_zip_file, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"\rProgress: {progress:.1f}%", end="")
            print("\nDownload completed!")

            # 解压zip文件
            print(f"Extracting {tmp_zip_file}...")
            with zipfile.ZipFile(tmp_zip_file, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            print("Extraction completed!")

            # 复制文件到目标目录
            print(f"Copying files to {actual_save_to}...")
            for item in tmp_dir.iterdir():
                if item.is_file() and item != tmp_zip_file:
                    shutil.copy2(item, actual_save_to)
                elif item.is_dir():
                    dest_dir = actual_save_to / item.name
                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)
                    shutil.copytree(item, dest_dir)

            print(f"Files saved to {actual_save_to}")

            # 清理临时文件
            shutil.rmtree(tmp_dir)

            return True

        except Exception as e:
            print(f"Error: {e}")
            return False
