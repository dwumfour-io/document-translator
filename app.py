from flask import Flask, render_template, request, jsonify, send_file
import os
import deepl
from werkzeug.utils import secure_filename
import tempfile
from dotenv import load_dotenv
import logging
from datetime import datetime
import uuid

# Load environment variables from .env file
load_dotenv()

# Configure logging
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f'translator_{datetime.now().strftime("%Y%m%d")}.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max for batch uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'translated'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# DeepL API configuration
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY', '')

if not DEEPL_API_KEY:
    logger.warning("DEEPL_API_KEY not set. Please create a .env file with your API key.")
    print("⚠️  Warning: DEEPL_API_KEY not set. Please create a .env file with your API key.")
    print("   See .env.example for the required format.")

# Supported file types for DeepL Document Translation
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'xlsx', 'txt', 'html'}

# Error messages for better UX
ERROR_MESSAGES = {
    'no_api_key': 'DeepL API key not configured. Please set DEEPL_API_KEY in your .env file.',
    'no_file': 'No file provided. Please select a file to upload.',
    'no_file_selected': 'No file selected. Please choose a file.',
    'invalid_file_type': 'Invalid file type. Supported formats: PDF, DOCX, PPTX, XLSX, TXT, HTML',
    'file_too_large': 'File is too large. Maximum size is 16MB per file.',
    'no_text': 'No text provided. Please enter some text to translate.',
    'translation_failed': 'Translation failed. Please try again.',
    'file_not_found': 'Translated file not found. It may have been deleted.',
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

@app.route('/')
def index():
    logger.info("Homepage accessed")
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'api_configured': bool(DEEPL_API_KEY)
    })

@app.route('/languages', methods=['GET'])
def get_languages():
    """Get available source and target languages from DeepL"""
    try:
        if not DEEPL_API_KEY:
            logger.error("Languages request failed: API key not configured")
            return jsonify({'error': ERROR_MESSAGES['no_api_key']}), 500
        
        translator = deepl.Translator(DEEPL_API_KEY)
        
        # Get source languages
        source_languages = [
            {'code': lang.code, 'name': lang.name}
            for lang in translator.get_source_languages()
        ]
        
        # Get target languages
        target_languages = [
            {'code': lang.code, 'name': lang.name}
            for lang in translator.get_target_languages()
        ]
        
        logger.info(f"Languages loaded: {len(source_languages)} source, {len(target_languages)} target")
        
        return jsonify({
            'source_languages': source_languages,
            'target_languages': target_languages
        })
    except deepl.AuthorizationException:
        logger.error("DeepL authorization failed - invalid API key")
        return jsonify({'error': 'Invalid DeepL API key. Please check your credentials.'}), 401
    except deepl.QuotaExceededException:
        logger.error("DeepL quota exceeded")
        return jsonify({'error': 'DeepL API quota exceeded. Please check your plan limits.'}), 429
    except Exception as e:
        logger.error(f"Languages request failed: {str(e)}")
        return jsonify({'error': f'Failed to load languages: {str(e)}'}), 500

@app.route('/translate-text', methods=['POST'])
def translate_text():
    """Translate plain text using DeepL API"""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        if not DEEPL_API_KEY:
            logger.error(f"[{request_id}] Text translation failed: API key not configured")
            return jsonify({'error': ERROR_MESSAGES['no_api_key']}), 500
        
        data = request.get_json()
        text = data.get('text', '')
        target_lang = data.get('target_lang', 'EN-US')
        source_lang = data.get('source_lang', None)
        formality = data.get('formality', 'default')
        
        if not text:
            logger.warning(f"[{request_id}] Text translation failed: No text provided")
            return jsonify({'error': ERROR_MESSAGES['no_text']}), 400
        
        char_count = len(text)
        logger.info(f"[{request_id}] Text translation started: {char_count} chars, target={target_lang}")
        
        translator = deepl.Translator(DEEPL_API_KEY)
        
        result = translator.translate_text(
            text,
            source_lang=source_lang if source_lang else None,
            target_lang=target_lang,
            formality=formality if formality != 'default' else None
        )
        
        logger.info(f"[{request_id}] Text translation completed: {source_lang or result.detected_source_lang} → {target_lang}")
        
        return jsonify({
            'success': True,
            'translated_text': result.text,
            'detected_source_lang': result.detected_source_lang,
            'character_count': char_count
        })
    
    except deepl.AuthorizationException:
        logger.error(f"[{request_id}] DeepL authorization failed")
        return jsonify({'error': 'Invalid DeepL API key. Please check your credentials.'}), 401
    except deepl.QuotaExceededException:
        logger.error(f"[{request_id}] DeepL quota exceeded")
        return jsonify({'error': 'DeepL API quota exceeded. Please upgrade your plan or wait for quota reset.'}), 429
    except Exception as e:
        logger.error(f"[{request_id}] Text translation failed: {str(e)}")
        return jsonify({'error': f'Translation failed: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_document():
    """Translate a single document using DeepL Document API"""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        if not DEEPL_API_KEY:
            logger.error(f"[{request_id}] Document upload failed: API key not configured")
            return jsonify({'error': ERROR_MESSAGES['no_api_key']}), 500
        
        if 'file' not in request.files:
            logger.warning(f"[{request_id}] Document upload failed: No file provided")
            return jsonify({'error': ERROR_MESSAGES['no_file']}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.warning(f"[{request_id}] Document upload failed: No file selected")
            return jsonify({'error': ERROR_MESSAGES['no_file_selected']}), 400
        
        if not allowed_file(file.filename):
            logger.warning(f"[{request_id}] Document upload failed: Invalid file type - {file.filename}")
            return jsonify({'error': ERROR_MESSAGES['invalid_file_type']}), 400
        
        target_lang = request.form.get('target_lang', 'EN-US')
        source_lang = request.form.get('source_lang', None)
        formality = request.form.get('formality', 'default')
        
        filename = secure_filename(file.filename)
        file_extension = get_file_extension(filename)
        
        logger.info(f"[{request_id}] Document translation started: {filename}, target={target_lang}")
        
        # Create temp file for input
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as input_file:
            file.save(input_file.name)
            input_path = input_file.name
        
        # Create output filename
        name_without_ext = filename.rsplit('.', 1)[0]
        output_filename = f"{name_without_ext}_{target_lang}.{file_extension}"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        try:
            translator = deepl.Translator(DEEPL_API_KEY)
            
            translator.translate_document_from_filepath(
                input_path,
                output_path,
                target_lang=target_lang,
                source_lang=source_lang if source_lang else None,
                formality=formality if formality != 'default' else None
            )
            
            os.unlink(input_path)
            
            logger.info(f"[{request_id}] Document translation completed: {filename} → {output_filename}")
            
            return jsonify({
                'success': True,
                'message': 'Document translated successfully!',
                'original_filename': filename,
                'translated_filename': output_filename,
                'download_url': f'/download/{output_filename}'
            })
            
        except deepl.DocumentTranslationException as e:
            if os.path.exists(input_path):
                os.unlink(input_path)
            logger.error(f"[{request_id}] Document translation failed: {str(e)}")
            raise Exception(f"Document translation failed: {str(e)}")
    
    except deepl.AuthorizationException:
        logger.error(f"[{request_id}] DeepL authorization failed")
        return jsonify({'error': 'Invalid DeepL API key. Please check your credentials.'}), 401
    except deepl.QuotaExceededException:
        logger.error(f"[{request_id}] DeepL quota exceeded")
        return jsonify({'error': 'DeepL API quota exceeded. Document translation requires more quota.'}), 429
    except Exception as e:
        logger.error(f"[{request_id}] Document upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload-batch', methods=['POST'])
def upload_batch():
    """Translate multiple documents at once"""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        if not DEEPL_API_KEY:
            logger.error(f"[{request_id}] Batch upload failed: API key not configured")
            return jsonify({'error': ERROR_MESSAGES['no_api_key']}), 500
        
        if 'files[]' not in request.files:
            logger.warning(f"[{request_id}] Batch upload failed: No files provided")
            return jsonify({'error': ERROR_MESSAGES['no_file']}), 400
        
        files = request.files.getlist('files[]')
        
        if not files or len(files) == 0:
            return jsonify({'error': ERROR_MESSAGES['no_file_selected']}), 400
        
        target_lang = request.form.get('target_lang', 'EN-US')
        source_lang = request.form.get('source_lang', None)
        formality = request.form.get('formality', 'default')
        
        logger.info(f"[{request_id}] Batch translation started: {len(files)} files, target={target_lang}")
        
        translator = deepl.Translator(DEEPL_API_KEY)
        results = []
        successful = 0
        failed = 0
        
        for file in files:
            if file.filename == '':
                continue
            
            if not allowed_file(file.filename):
                results.append({
                    'original_filename': file.filename,
                    'success': False,
                    'error': 'Invalid file type'
                })
                failed += 1
                continue
            
            filename = secure_filename(file.filename)
            file_extension = get_file_extension(filename)
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as input_file:
                    file.save(input_file.name)
                    input_path = input_file.name
                
                name_without_ext = filename.rsplit('.', 1)[0]
                output_filename = f"{name_without_ext}_{target_lang}.{file_extension}"
                output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                
                translator.translate_document_from_filepath(
                    input_path,
                    output_path,
                    target_lang=target_lang,
                    source_lang=source_lang if source_lang else None,
                    formality=formality if formality != 'default' else None
                )
                
                os.unlink(input_path)
                
                results.append({
                    'original_filename': filename,
                    'translated_filename': output_filename,
                    'download_url': f'/download/{output_filename}',
                    'success': True
                })
                successful += 1
                logger.info(f"[{request_id}] Batch item completed: {filename}")
                
            except Exception as e:
                if 'input_path' in locals() and os.path.exists(input_path):
                    os.unlink(input_path)
                results.append({
                    'original_filename': filename,
                    'success': False,
                    'error': str(e)
                })
                failed += 1
                logger.error(f"[{request_id}] Batch item failed: {filename} - {str(e)}")
        
        logger.info(f"[{request_id}] Batch translation completed: {successful} successful, {failed} failed")
        
        return jsonify({
            'success': failed == 0,
            'message': f'Translated {successful} of {successful + failed} files',
            'results': results,
            'summary': {
                'total': successful + failed,
                'successful': successful,
                'failed': failed
            }
        })
    
    except deepl.AuthorizationException:
        logger.error(f"[{request_id}] DeepL authorization failed")
        return jsonify({'error': 'Invalid DeepL API key. Please check your credentials.'}), 401
    except deepl.QuotaExceededException:
        logger.error(f"[{request_id}] DeepL quota exceeded")
        return jsonify({'error': 'DeepL API quota exceeded. Try with fewer files.'}), 429
    except Exception as e:
        logger.error(f"[{request_id}] Batch upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download the translated document"""
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(file_path):
            logger.warning(f"Download failed: File not found - {filename}")
            return jsonify({'error': ERROR_MESSAGES['file_not_found']}), 404
        
        logger.info(f"File downloaded: {filename}")
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning("Upload rejected: File too large")
    return jsonify({'error': 'File is too large. Maximum size is 50MB total for batch uploads.'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

if __name__ == '__main__':
    logger.info("Document Translator started on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
