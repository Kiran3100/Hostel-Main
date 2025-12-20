"""
Document Processing Service

Document OCR, verification workflows, compliance checking, and expiry tracking.
"""

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
import logging
import re

from sqlalchemy.orm import Session

from app.repositories.file_management.document_upload_repository import (
    DocumentUploadRepository,
)
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.services.file_management.file_storage_service import FileStorageService
from app.core.exceptions import ProcessingException, NotFoundException

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """
    Service for document processing operations including OCR and verification.
    """

    # Document type patterns for classification
    DOCUMENT_PATTERNS = {
        'aadhaar': [
            r'\b\d{4}\s\d{4}\s\d{4}\b',  # Aadhaar number pattern
            r'Unique\s+Identification\s+Authority',
            r'UIDAI',
        ],
        'pan': [
            r'\b[A-Z]{5}\d{4}[A-Z]\b',  # PAN pattern
            r'Permanent\s+Account\s+Number',
            r'Income\s+Tax\s+Department',
        ],
        'passport': [
            r'PASSPORT',
            r'Republic\s+of\s+India',
            r'\b[A-Z]\d{7}\b',  # Passport number
        ],
        'driving_license': [
            r'Driving\s+Licence',
            r'DL\s+No',
            r'Transport\s+Department',
        ],
    }

    def __init__(
        self,
        db_session: Session,
        storage_service: FileStorageService,
    ):
        self.db = db_session
        self.document_repo = DocumentUploadRepository(db_session)
        self.file_repo = FileUploadRepository(db_session)
        self.storage = storage_service

    # ============================================================================
    # DOCUMENT UPLOAD CREATION
    # ============================================================================

    async def create_document_upload(
        self,
        file_id: str,
        document_data: Dict[str, Any],
        uploaded_by_user_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create document upload with automatic type detection and processing.

        Args:
            file_id: Associated file upload ID
            document_data: Document metadata
            uploaded_by_user_id: User uploading document
            audit_context: Audit context

        Returns:
            Document upload details with processing status
        """
        try:
            logger.info(f"Creating document upload for file: {file_id}")

            # Generate document ID if not provided
            if 'document_id' not in document_data:
                document_data['document_id'] = f"DOC-{datetime.utcnow().strftime('%Y%m%d')}-{file_id[:8]}"

            # Validate document type
            doc_type = await self.document_repo.get_document_type(
                document_data['document_type']
            )
            if not doc_type:
                raise ProcessingException(
                    f"Invalid document type: {document_data['document_type']}"
                )

            # Create document upload
            document_upload = await self.document_repo.create_document_upload(
                file_id=file_id,
                document_data=document_data,
                uploaded_by_user_id=uploaded_by_user_id,
                audit_context=audit_context,
            )

            # Queue for OCR if enabled
            if document_upload.enable_ocr:
                await self._queue_ocr_processing(document_upload)

            logger.info(f"Document upload created: {document_upload.document_id}")

            return {
                "document_id": document_upload.document_id,
                "file_id": file_id,
                "document_type": document_upload.document_type,
                "ocr_queued": document_upload.enable_ocr,
                "verification_status": document_upload.verification_status,
            }

        except Exception as e:
            logger.error(f"Failed to create document upload: {str(e)}", exc_info=True)
            raise ProcessingException(f"Document upload creation failed: {str(e)}")

    # ============================================================================
    # OCR PROCESSING
    # ============================================================================

    async def process_document_ocr(
        self,
        document_id: str,
        language: str = 'eng',
    ) -> Dict[str, Any]:
        """
        Perform OCR on document.

        Args:
            document_id: Document identifier (document_id field)
            language: OCR language (default: English)

        Returns:
            OCR results with extracted text and fields

        Raises:
            NotFoundException: If document not found
            ProcessingException: If OCR fails
        """
        try:
            logger.info(f"Processing OCR for document: {document_id}")

            # Get document
            document = await self.document_repo.find_by_document_id(document_id)
            if not document:
                raise NotFoundException(f"Document not found: {document_id}")

            # Update status to processing
            await self.document_repo.update_ocr_status(
                document_id=document.id,
                status="processing",
            )

            # Get file content
            file_upload = await self.file_repo.find_by_file_id(document.file_id)
            file_content = await self.storage.download_file(file_upload.storage_key)

            # Perform OCR based on file type
            start_time = datetime.utcnow()
            
            if file_upload.content_type == 'application/pdf':
                ocr_result = await self._ocr_pdf(file_content, language)
            elif file_upload.content_type.startswith('image/'):
                ocr_result = await self._ocr_image(file_content, language)
            else:
                raise ProcessingException(
                    f"Unsupported content type for OCR: {file_upload.content_type}"
                )

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Extract structured fields
            extracted_fields = await self._extract_document_fields(
                text=ocr_result['full_text'],
                document_type=document.document_type,
            )

            # Detect document subtype if not set
            if not document.document_subtype:
                detected_subtype = await self._detect_document_subtype(
                    ocr_result['full_text']
                )
                if detected_subtype:
                    document.document_subtype = detected_subtype
                    self.db.commit()

            # Store OCR results
            ocr_data = {
                "ocr_status": "completed",
                "confidence_score": ocr_result.get('confidence'),
                "full_text": ocr_result['full_text'],
                "extracted_fields": extracted_fields,
                "extracted_name": extracted_fields.get('name'),
                "extracted_id_number": extracted_fields.get('id_number'),
                "extracted_dob": extracted_fields.get('dob'),
                "extracted_address": extracted_fields.get('address'),
                "extracted_issue_date": extracted_fields.get('issue_date'),
                "extracted_expiry_date": extracted_fields.get('expiry_date'),
                "ocr_engine": "tesseract",
                "ocr_engine_version": pytesseract.get_tesseract_version(),
                "language_detected": language,
                "processing_time_seconds": processing_time,
                "total_pages": ocr_result.get('total_pages', 1),
                "pages_data": ocr_result.get('pages_data', []),
            }

            await self.document_repo.create_ocr_result(
                document_id=document.id,
                ocr_data=ocr_data,
            )

            logger.info(f"OCR completed for document: {document_id}")

            return {
                "document_id": document_id,
                "status": "completed",
                "text_length": len(ocr_result['full_text']),
                "confidence": ocr_result.get('confidence'),
                "extracted_fields": extracted_fields,
                "processing_time_seconds": processing_time,
            }

        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}", exc_info=True)
            
            # Update status to failed
            await self.document_repo.update_ocr_status(
                document_id=document.id,
                status="failed",
                error_message=str(e),
            )
            
            raise ProcessingException(f"OCR processing failed: {str(e)}")

    async def _ocr_image(
        self,
        image_content: bytes,
        language: str,
    ) -> Dict[str, Any]:
        """Perform OCR on image."""
        img = Image.open(io.BytesIO(image_content))
        
        # Preprocess image for better OCR
        img = self._preprocess_image_for_ocr(img)
        
        # Perform OCR
        text = pytesseract.image_to_string(img, lang=language)
        
        # Get confidence data
        data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "full_text": text.strip(),
            "confidence": round(avg_confidence, 2),
            "total_pages": 1,
        }

    async def _ocr_pdf(
        self,
        pdf_content: bytes,
        language: str,
    ) -> Dict[str, Any]:
        """Perform OCR on PDF."""
        # Convert PDF to images
        images = convert_from_bytes(pdf_content, dpi=300)
        
        full_text = []
        pages_data = []
        all_confidences = []

        for page_num, img in enumerate(images, 1):
            # Preprocess
            img = self._preprocess_image_for_ocr(img)
            
            # OCR
            page_text = pytesseract.image_to_string(img, lang=language)
            full_text.append(page_text)
            
            # Get confidence
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            page_confidence = sum(confidences) / len(confidences) if confidences else 0
            all_confidences.extend(confidences)
            
            pages_data.append({
                "page_number": page_num,
                "text": page_text.strip(),
                "confidence": round(page_confidence, 2),
            })

        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0

        return {
            "full_text": "\n\n".join(full_text).strip(),
            "confidence": round(avg_confidence, 2),
            "total_pages": len(images),
            "pages_data": pages_data,
        }

    def _preprocess_image_for_ocr(self, img: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results."""
        # Convert to grayscale
        img = img.convert('L')
        
        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        return img

    async def _extract_document_fields(
        self,
        text: str,
        document_type: str,
    ) -> Dict[str, Any]:
        """Extract structured fields from OCR text."""
        fields = {}

        # Extract name (usually in all caps at the beginning)
        name_pattern = r'\b([A-Z][A-Z\s]{5,50})\b'
        name_match = re.search(name_pattern, text)
        if name_match:
            fields['name'] = name_match.group(1).strip()

        # Extract dates (DD/MM/YYYY or DD-MM-YYYY)
        date_pattern = r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b'
        dates = re.findall(date_pattern, text)
        if dates:
            # Try to identify which date is what
            if 'DOB' in text or 'Birth' in text:
                dob_index = text.find('DOB') or text.find('Birth')
                for date_str in dates:
                    if text.find(date_str) > dob_index:
                        fields['dob'] = date_str
                        break

        # Extract Aadhaar number
        aadhaar_pattern = r'\b(\d{4}\s\d{4}\s\d{4})\b'
        aadhaar_match = re.search(aadhaar_pattern, text)
        if aadhaar_match:
            fields['id_number'] = aadhaar_match.group(1)

        # Extract PAN number
        pan_pattern = r'\b([A-Z]{5}\d{4}[A-Z])\b'
        pan_match = re.search(pan_pattern, text)
        if pan_match:
            fields['id_number'] = pan_match.group(1)

        # Extract address (text between certain keywords)
        address_pattern = r'(?:Address|Permanent Address)[\s:]+(.+?)(?:\n\n|Father|Mother|DOB|$)'
        address_match = re.search(address_pattern, text, re.DOTALL | re.IGNORECASE)
        if address_match:
            fields['address'] = address_match.group(1).strip()

        return fields

    async def _detect_document_subtype(self, text: str) -> Optional[str]:
        """Detect document subtype from OCR text."""
        for subtype, patterns in self.DOCUMENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return subtype
        return None

    async def _queue_ocr_processing(self, document: Any) -> None:
        """Queue document for OCR processing."""
        # In a production system, this would add to a task queue (Celery, etc.)
        # For now, we just log it
        logger.info(f"OCR queued for document: {document.document_id}")

    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================

    async def verify_document(
        self,
        document_id: str,
        verification_data: Dict[str, Any],
        verified_by_user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify document with decision and notes.

        Args:
            document_id: Document identifier
            verification_data: Verification decision and details
            verified_by_user_id: User performing verification
            ip_address: Verifier IP address
            user_agent: Verifier user agent

        Returns:
            Verification result

        Raises:
            NotFoundException: If document not found
        """
        try:
            logger.info(f"Verifying document: {document_id}")

            # Get document
            document = await self.document_repo.find_by_document_id(document_id)
            if not document:
                raise NotFoundException(f"Document not found: {document_id}")

            # Create verification record
            verification = await self.document_repo.create_verification(
                document_id=document.id,
                verification_data=verification_data,
                verified_by_user_id=verified_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(
                f"Document verified: {document_id}, status: {verification_data['verification_status']}"
            )

            return {
                "document_id": document_id,
                "verification_status": verification_data['verification_status'],
                "verified_by": verified_by_user_id,
                "verified_at": verification.verified_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Document verification failed: {str(e)}", exc_info=True)
            raise ProcessingException(f"Document verification failed: {str(e)}")

    async def auto_verify_document(
        self,
        document_id: str,
        system_user_id: str,
    ) -> Dict[str, Any]:
        """
        Attempt automatic document verification based on OCR and validation.

        Args:
            document_id: Document identifier
            system_user_id: System user ID for auto-verification

        Returns:
            Auto-verification result
        """
        try:
            logger.info(f"Auto-verifying document: {document_id}")

            # Get document with OCR results
            document = await self.document_repo.find_by_document_id(
                document_id=document_id,
                load_relationships=True,
            )
            if not document:
                raise NotFoundException(f"Document not found: {document_id}")

            # Check if OCR completed
            if not document.ocr_completed:
                return {
                    "auto_verified": False,
                    "reason": "OCR not completed",
                }

            ocr_result = document.ocr_result
            if not ocr_result:
                return {
                    "auto_verified": False,
                    "reason": "No OCR results available",
                }

            # Calculate authenticity score
            authenticity_score = await self._calculate_authenticity_score(
                document=document,
                ocr_result=ocr_result,
            )

            # Auto-verify if score is high enough
            threshold = 80  # 80% confidence threshold
            
            if authenticity_score >= threshold:
                verification_data = {
                    "verification_status": "approved",
                    "verification_type": "automated",
                    "verification_notes": f"Auto-verified with {authenticity_score}% confidence",
                    "authenticity_score": authenticity_score,
                    "verification_checklist": {
                        "ocr_confidence": ocr_result.confidence_score,
                        "field_extraction": len(ocr_result.extracted_fields or {}),
                        "document_type_match": bool(document.document_subtype),
                    },
                }

                await self.document_repo.create_verification(
                    document_id=document.id,
                    verification_data=verification_data,
                    verified_by_user_id=system_user_id,
                )

                return {
                    "auto_verified": True,
                    "authenticity_score": authenticity_score,
                    "verification_status": "approved",
                }
            else:
                return {
                    "auto_verified": False,
                    "reason": f"Authenticity score too low: {authenticity_score}%",
                    "requires_manual_review": True,
                }

        except Exception as e:
            logger.error(f"Auto-verification failed: {str(e)}", exc_info=True)
            return {
                "auto_verified": False,
                "reason": f"Error: {str(e)}",
            }

    async def _calculate_authenticity_score(
        self,
        document: Any,
        ocr_result: Any,
    ) -> int:
        """Calculate document authenticity score (0-100)."""
        score = 0
        max_score = 100

        # OCR confidence (40 points)
        if ocr_result.confidence_score:
            score += int((ocr_result.confidence_score / 100) * 40)

        # Field extraction completeness (30 points)
        expected_fields = ['name', 'id_number']
        extracted_fields = ocr_result.extracted_fields or {}
        extracted_count = sum(1 for field in expected_fields if field in extracted_fields)
        score += int((extracted_count / len(expected_fields)) * 30)

        # Document type detection (20 points)
        if document.document_subtype:
            score += 20

        # Text quality (10 points)
        if ocr_result.full_text and len(ocr_result.full_text) > 100:
            score += 10

        return min(score, max_score)

    # ============================================================================
    # EXPIRY TRACKING
    # ============================================================================

    async def track_document_expiry(
        self,
        document_id: str,
    ) -> Dict[str, Any]:
        """
        Update expiry tracking for document.

        Args:
            document_id: Document identifier

        Returns:
            Expiry status
        """
        try:
            document = await self.document_repo.find_by_document_id(document_id)
            if not document:
                raise NotFoundException(f"Document not found: {document_id}")

            if not document.expiry_tracking:
                return {
                    "tracked": False,
                    "reason": "No expiry tracking configured",
                }

            # Update expiry calculations
            expiry = document.expiry_tracking
            days_until_expiry = (expiry.expiry_date - date.today()).days

            return {
                "tracked": True,
                "document_id": document_id,
                "expiry_date": expiry.expiry_date.isoformat(),
                "days_until_expiry": days_until_expiry,
                "is_expired": expiry.is_expired,
                "urgency_level": expiry.urgency_level,
            }

        except Exception as e:
            logger.error(f"Expiry tracking failed: {str(e)}", exc_info=True)
            raise ProcessingException(f"Expiry tracking failed: {str(e)}")

    async def process_expiry_alerts(
        self,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Process and send expiry alerts.

        Args:
            batch_size: Number of alerts to process

        Returns:
            Processing results
        """
        try:
            logger.info("Processing document expiry alerts")

            # Update expiry calculations
            updated_count = await self.document_repo.update_expiry_calculations(
                batch_size=batch_size
            )

            # Send alerts
            alerts_sent = await self.document_repo.send_expiry_alerts(
                batch_size=batch_size
            )

            logger.info(f"Expiry alerts processed: {alerts_sent} alerts sent")

            return {
                "expiry_calculations_updated": updated_count,
                "alerts_sent": alerts_sent,
            }

        except Exception as e:
            logger.error(f"Expiry alert processing failed: {str(e)}", exc_info=True)
            raise ProcessingException(f"Expiry alert processing failed: {str(e)}")

    # ============================================================================
    # COMPLIANCE CHECKING
    # ============================================================================

    async def check_student_compliance(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """
        Check student document compliance.

        Args:
            student_id: Student identifier

        Returns:
            Compliance status and missing documents
        """
        try:
            compliance = await self.document_repo.check_student_document_compliance(
                student_id=student_id
            )

            return compliance

        except Exception as e:
            logger.error(f"Compliance check failed: {str(e)}", exc_info=True)
            raise ProcessingException(f"Compliance check failed: {str(e)}")

    async def get_compliance_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate compliance report.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Compliance report with statistics
        """
        try:
            # Get document statistics
            doc_stats = await self.document_repo.get_document_statistics(
                start_date=start_date,
                end_date=end_date,
            )

            # Get verification statistics
            verification_stats = await self.document_repo.get_verification_statistics(
                start_date=start_date,
                end_date=end_date,
            )

            # Get expiry summary
            expiry_summary = await self.document_repo.get_expiry_summary()

            # Get pending items
            pending_verification = await self.document_repo.find_documents_pending_verification(
                limit=100
            )
            
            expiring_soon = await self.document_repo.find_expiring_documents(
                days_threshold=30,
                limit=100,
            )

            return {
                "report_generated_at": datetime.utcnow().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "documents": doc_stats,
                "verification": verification_stats,
                "expiry": expiry_summary,
                "pending_actions": {
                    "pending_verification": len(pending_verification),
                    "expiring_soon": len(expiring_soon),
                },
            }

        except Exception as e:
            logger.error(f"Compliance report generation failed: {str(e)}", exc_info=True)
            raise ProcessingException(f"Compliance report generation failed: {str(e)}")

    # ============================================================================
    # BATCH PROCESSING
    # ============================================================================

    async def process_ocr_queue(
        self,
        max_documents: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Process pending OCR queue.

        Args:
            max_documents: Maximum documents to process

        Returns:
            List of processing results
        """
        results = []

        # Get pending documents
        pending_docs = await self.document_repo.find_documents_pending_ocr(
            limit=max_documents,
            priority_document_types=['id_proof', 'address_proof'],
        )

        for document in pending_docs:
            try:
                result = await self.process_document_ocr(
                    document_id=document.document_id
                )
                results.append(result)

            except Exception as e:
                logger.error(f"OCR processing failed for {document.document_id}: {str(e)}")
                results.append({
                    "document_id": document.document_id,
                    "status": "failed",
                    "error": str(e),
                })

        return results