"""
Markdown document chunking module with token-aware sliding window.
"""

import re
from typing import List, Dict, Any
from src.rag.token_counter import count_tokens
from src.config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS


class PolicyChunk:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        policy_name: str,
        section_title: str,
        text: str,
        token_count: int,
        chunk_index: int,
        company_id: str = "company_x",
        version: int = 1,
        is_active: bool = True,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.policy_name = policy_name
        self.section_title = section_title
        self.text = text
        self.token_count = token_count
        self.chunk_index = chunk_index
        self.company_id = company_id
        self.version = version
        self.is_active = is_active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "policy_name": self.policy_name,
            "section_title": self.section_title,
            "text": self.text,
            "token_count": self.token_count,
            "chunk_index": self.chunk_index,
            "company_id": self.company_id,
            "version": self.version,
            "is_active": self.is_active,
        }


def chunk_markdown_document(
    markdown_text: str,
    document_id: str,
    policy_name: str,
    target_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
    company_id: str = "company_x",
    version: int = 1,
    is_active: bool = True,
) -> List[PolicyChunk]:
    """
    Chunks a markdown document preserving header context and adhering to token bounds.
    """
    sections = re.split(r"(^##?\s+[^\n]+)", markdown_text, flags=re.MULTILINE)
    
    # Reassemble header + content blocks
    blocks = []
    current_header = "General"
    i = 0
    while i < len(sections):
        part = sections[i].strip()
        if not part:
            i += 1
            continue
        if part.startswith("#"):
            current_header = part.lstrip("#").strip()
            if i + 1 < len(sections):
                content = sections[i + 1].strip()
                blocks.append((current_header, f"{part}\n\n{content}"))
                i += 2
                continue
            else:
                blocks.append((current_header, part))
                i += 1
                continue
        else:
            blocks.append((current_header, part))
            i += 1

    chunks: List[PolicyChunk] = []
    chunk_index = 0

    for header, content in blocks:
        tokens = count_tokens(content)
        if tokens <= target_tokens or target_tokens <= 0:
            cid = f"{document_id}-chk-{chunk_index:03d}"
            chunks.append(
                PolicyChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    policy_name=policy_name,
                    section_title=header,
                    text=content,
                    token_count=tokens,
                    chunk_index=chunk_index,
                    company_id=company_id,
                    version=version,
                    is_active=is_active,
                )
            )
            chunk_index += 1
        else:
            # Paragraph-based or window-based subdivision
            paragraphs = content.split("\n\n")
            curr_text = ""
            for para in paragraphs:
                candidate = (curr_text + "\n\n" + para).strip() if curr_text else para
                if count_tokens(candidate) > target_tokens and curr_text:
                    cid = f"{document_id}-chk-{chunk_index:03d}"
                    chunks.append(
                        PolicyChunk(
                            chunk_id=cid,
                            document_id=document_id,
                            policy_name=policy_name,
                            section_title=header,
                            text=curr_text,
                            token_count=count_tokens(curr_text),
                            chunk_index=chunk_index,
                            company_id=company_id,
                            version=version,
                            is_active=is_active,
                        )
                    )
                    chunk_index += 1
                    # Retain last few words/lines for overlap
                    words = curr_text.split()
                    overlap_words = " ".join(words[-max(1, overlap_tokens):])
                    curr_text = (overlap_words + "\n\n" + para).strip()
                else:
                    curr_text = candidate

            if curr_text.strip():
                cid = f"{document_id}-chk-{chunk_index:03d}"
                chunks.append(
                    PolicyChunk(
                        chunk_id=cid,
                        document_id=document_id,
                        policy_name=policy_name,
                        section_title=header,
                        text=curr_text,
                        token_count=count_tokens(curr_text),
                        chunk_index=chunk_index,
                        company_id=company_id,
                        version=version,
                        is_active=is_active,
                    )
                )
                chunk_index += 1

    return chunks
