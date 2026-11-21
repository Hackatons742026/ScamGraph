# Licences

This is an inventory of direct runtime and development dependencies declared in the repository, plus external tools called by the pipeline. Confirm the license metadata for the exact resolved versions in each release environment and include notices required by the package distributions. This is not legal advice and does not replace a transitive dependency/SBOM audit.

## Python packages

| Package | Use | Declared license | Source |
|---|---|---|---|
| FastAPI | HTTP API | MIT | [PyPI](https://pypi.org/project/fastapi/) |
| Uvicorn | ASGI server | BSD-3-Clause | [PyPI](https://pypi.org/project/uvicorn/) |
| Pydantic | Validation and schemas | MIT | [PyPI](https://pypi.org/project/pydantic/) |
| HTTPX | API/test client | BSD-3-Clause | [PyPI](https://pypi.org/project/httpx/) |
| pytest | Tests | MIT | [PyPI](https://pypi.org/project/pytest/) |
| Pillow | Image handling | MIT-CMU | [PyPI](https://pypi.org/project/pillow/) |
| pytesseract | Tesseract wrapper | Apache-2.0 | [PyPI](https://pypi.org/project/pytesseract/) |
| ImageHash | Perceptual image hashes | BSD-2-Clause | [PyPI](https://pypi.org/project/ImageHash/) |
| EasyOCR (optional) | Neural OCR | Apache-2.0 | [PyPI](https://pypi.org/project/easyocr/) |
| PyTorch (optional) | EasyOCR runtime | BSD-3-Clause | [PyPI](https://pypi.org/project/torch/) |
| faster-whisper (optional) | Speech transcription | MIT | [PyPI](https://pypi.org/project/faster-whisper/) |

Python package dependencies are ranges in `backend/requirements*.txt`; generated lockfiles are not currently committed. The frontend dependency manifest is `frontend/package.json`; each resolved npm package has its own license and must be included in a release-level third-party inventory.

## Frontend direct runtime packages

The frontend manifest lists these direct runtime dependencies. License metadata links below point to their npm package records; check the exact locked package and transitive notices before redistribution.

| Package(s) | Declared license | Source |
|---|---|---|
| `@radix-ui/react-tabs` | MIT | [npm](https://www.npmjs.com/package/@radix-ui/react-tabs) |
| `@tanstack/react-query` | MIT | [npm](https://www.npmjs.com/package/@tanstack/react-query) |
| `react`, `react-dom` | MIT | [react](https://www.npmjs.com/package/react), [react-dom](https://www.npmjs.com/package/react-dom) |
| `react-router` | MIT | [npm](https://www.npmjs.com/package/react-router) |
| `openapi-fetch` | MIT | [npm](https://www.npmjs.com/package/openapi-fetch) |
| `tailwind-merge` | MIT | [npm](https://www.npmjs.com/package/tailwind-merge) |
| `clsx` | MIT | [npm](https://www.npmjs.com/package/clsx) |
| `class-variance-authority` | Apache-2.0 | [npm](https://www.npmjs.com/package/class-variance-authority) |
| `lucide-react` | ISC | [npm](https://www.npmjs.com/package/lucide-react) |

## External tools and model assets

| Component | Use | License / notice |
|---|---|---|
| FFmpeg | Video frame extraction | Build-dependent; commonly LGPL-2.1-or-later, with GPL components if enabled. Check the exact binary/build configuration and its `-L` output. |
| Tesseract OCR | OCR engine | Apache-2.0; language data has separate notices. |
| `tesseract-ocr-pol` | Polish OCR data | Check the installed distro package and upstream traineddata notice before redistribution. |
| EasyOCR model weights (optional) | Neural OCR | Check each downloaded model's upstream license and terms; package license alone does not license model weights. |
| SQLite | Local database | Public domain. |

The core pipeline does not download models or call remote services. Optional model packages and weights should only be installed or redistributed after their individual licenses are recorded.

## Project code and notices

No project-level license file is currently present. Before distributing this repository, the project owner should select and add a license for ScamGraph source code, then preserve upstream notices for bundled dependencies/assets. No dataset or third-party capture content is licensed by this document.
