from flask import Flask, request, jsonify
from cogniac import CogniacConnection, CogniacMedia, CogniacSubject
import os
from dotenv import load_dotenv
from flask_cors import CORS
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Get environment variables
COG_USER = os.getenv('COG_USER')
COG_PASS = os.getenv('COG_PASS')
COG_TENANT = os.getenv('COG_TENANT')
SUBJECT_UID = 'text1_1swflmmt'  # Change this as needed

# Initialize Cogniac connection
cc = CogniacConnection(username=COG_USER, password=COG_PASS, tenant_id=COG_TENANT)
print(f"Connection successful to {cc}")

# Get or create subject
try:
    subject = CogniacSubject.get(cc, SUBJECT_UID)
    print(f"Found existing subject: {subject.subject_uid}")
except Exception:
    subject = CogniacSubject.create(cc, uid=SUBJECT_UID, name='Training Subject', consensus=True)
    print(f"Created new subject: {subject.subject_uid}")

# Store upload progress
upload_progress = {}

def upload_single_image(file_data, meta_tags, batch_id):
    """Upload a single image and return result"""
    temp_dir = os.path.join(os.getcwd(), "temp_uploads", batch_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = file_data['filename']
    temp_path = os.path.join(temp_dir, filename)
    
    try:
        # Save the file
        file_data['file'].save(temp_path)
        
        # Upload to Cogniac
        try:
            # Method 1: Try the standard create and associate approach
            media = CogniacMedia.create(
                cc,
                filename=temp_path,
                meta_tags=meta_tags,
                force_set='training'
            )
            subject.associate_media(media)
            
        except Exception as e1:
            try:
                # Method 2: Try creating media with different parameters
                media = CogniacMedia.create(
                    cc,
                    filename=temp_path,
                    meta_tags=meta_tags
                )
                subject.associate_media(media)
                
            except Exception as e2:
                try:
                    # Method 3: Try uploading directly through connection
                    with open(temp_path, 'rb') as f:
                        media = cc.upload_media(
                            f,
                            filename=filename,
                            meta_tags=meta_tags,
                            subject_uid=subject.subject_uid
                        )
                except Exception as e3:
                    raise Exception(f"All upload methods failed. Last error: {str(e3)}")
        
        return {
            'status': 'success',
            'filename': filename,
            'media_id': media.media_id
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'filename': filename,
            'error': str(e)
        }
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/upload', methods=['POST'])
def upload_image():
    """Single image upload endpoint"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file in request'}), 400

    img = request.files['image']
    filename = img.filename

    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    # Save temporarily in a safe directory
    temp_dir = os.path.join(os.getcwd(), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, filename)
    img.save(temp_path)

    try:
        # Get meta_tags from form data
        meta_tags = request.form.getlist('meta_tags')
        if not meta_tags:
            meta_tags = []
            for key, value in request.form.items():
                if key != 'image':
                    meta_tags.append(f"{key}:{value}")

        # Alternative approach - upload media and then associate with subject
        try:
            media = CogniacMedia.create(
                cc,
                filename=temp_path,
                meta_tags=meta_tags,
                force_set='training'
            )
            subject.associate_media(media)
            
        except Exception as e1:
            try:
                media = CogniacMedia.create(
                    cc,
                    filename=temp_path,
                    meta_tags=meta_tags
                )
                subject.associate_media(media)
                
            except Exception as e2:
                try:
                    with open(temp_path, 'rb') as f:
                        media = cc.upload_media(
                            f,
                            filename=filename,
                            meta_tags=meta_tags,
                            subject_uid=subject.subject_uid
                        )
                        
                except Exception as e3:
                    raise Exception(f"All upload methods failed. Last error: {str(e3)}")
        
        print(f"Successfully uploaded media: {media.media_id}")
        
        return jsonify({
            'media_id': media.media_id,
            'subject_uid': subject.subject_uid,
            'filename': filename,
            'meta_tags': meta_tags,
            'status': 'uploaded successfully'
        })
        
    except Exception as e:
        print(f"Error uploading media: {str(e)}")
        return jsonify({'error': f'Failed to upload media: {str(e)}'}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/batch-upload', methods=['POST'])
def batch_upload():
    """Batch upload endpoint for multiple images"""
    files = request.files.getlist('images')
    
    if not files:
        return jsonify({'error': 'No image files in request'}), 400
    
    if len(files) > 500:
        return jsonify({'error': 'Maximum 500 images allowed per batch'}), 400
    
    # Generate batch ID
    batch_id = f"batch_{int(time.time())}"
    
    # Get meta_tags from form data
    meta_tags = request.form.getlist('meta_tags')
    if not meta_tags:
        meta_tags = []
        for key, value in request.form.items():
            if key not in ['images']:
                meta_tags.append(f"{key}:{value}")
    
    # Initialize progress tracking
    upload_progress[batch_id] = {
        'total': len(files),
        'completed': 0,
        'successful': 0,
        'failed': 0,
        'status': 'processing',
        'results': []
    }
    
    # Prepare file data
    file_data_list = []
    for file in files:
        if file.filename:
            file_data_list.append({
                'file': file,
                'filename': file.filename
            })
    
    def process_batch():
        """Process batch upload in background"""
        successful_uploads = []
        failed_uploads = []
        
        # Use ThreadPoolExecutor for parallel uploads (be careful with rate limits)
        max_workers = min(10, len(file_data_list))  # Limit concurrent uploads
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(upload_single_image, file_data, meta_tags, batch_id): file_data
                for file_data in file_data_list
            }
            
            # Process completed uploads
            for future in as_completed(future_to_file):
                file_data = future_to_file[future]
                try:
                    result = future.result()
                    
                    if result['status'] == 'success':
                        successful_uploads.append(result)
                        upload_progress[batch_id]['successful'] += 1
                    else:
                        failed_uploads.append(result)
                        upload_progress[batch_id]['failed'] += 1
                    
                    upload_progress[batch_id]['completed'] += 1
                    upload_progress[batch_id]['results'].append(result)
                    
                except Exception as e:
                    failed_uploads.append({
                        'status': 'error',
                        'filename': file_data['filename'],
                        'error': str(e)
                    })
                    upload_progress[batch_id]['failed'] += 1
                    upload_progress[batch_id]['completed'] += 1
        
        # Update final status
        upload_progress[batch_id]['status'] = 'completed'
        
        # Clean up temp directory
        temp_dir = os.path.join(os.getcwd(), "temp_uploads", batch_id)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except:
                pass  # Directory might not be empty, that's okay
    
    # Start batch processing in background
    thread = threading.Thread(target=process_batch)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'batch_id': batch_id,
        'total_files': len(file_data_list),
        'status': 'processing',
        'message': 'Batch upload started. Use /batch-status/{batch_id} to check progress.'
    })

@app.route('/batch-status/<batch_id>', methods=['GET'])
def get_batch_status(batch_id):
    """Get batch upload status"""
    if batch_id not in upload_progress:
        return jsonify({'error': 'Batch ID not found'}), 404
    
    progress = upload_progress[batch_id]
    
    return jsonify({
        'batch_id': batch_id,
        'status': progress['status'],
        'total': progress['total'],
        'completed': progress['completed'],
        'successful': progress['successful'],
        'failed': progress['failed'],
        'progress_percentage': (progress['completed'] / progress['total']) * 100,
        'results': progress['results']
    })

@app.route('/upload-folder', methods=['POST'])
def upload_folder():
    """Upload all images from a specified folder"""
    data = request.get_json()
    
    if not data or 'folder_path' not in data:
        return jsonify({'error': 'folder_path is required in JSON body'}), 400
    
    folder_path = data['folder_path']
    
    if not os.path.exists(folder_path):
        return jsonify({'error': 'Folder path does not exist'}), 400
    
    # Get all image files from folder
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    image_files = []
    
    for filename in os.listdir(folder_path):
        if any(filename.lower().endswith(ext) for ext in image_extensions):
            image_files.append(os.path.join(folder_path, filename))
    
    if not image_files:
        return jsonify({'error': 'No image files found in the folder'}), 400
    
    if len(image_files) > 500:
        return jsonify({'error': f'Too many images ({len(image_files)}). Maximum 500 allowed.'}), 400
    
    # Generate batch ID
    batch_id = f"folder_batch_{int(time.time())}"
    
    # Get meta_tags from request
    meta_tags = data.get('meta_tags', [])
    
    # Initialize progress tracking
    upload_progress[batch_id] = {
        'total': len(image_files),
        'completed': 0,
        'successful': 0,
        'failed': 0,
        'status': 'processing',
        'results': []
    }
    
    def upload_single_image_from_path(file_path, meta_tags, batch_id):
        """Upload a single image from file path"""
        filename = os.path.basename(file_path)
        
        try:
            # Upload to Cogniac
            try:
                # Method 1: Try the standard create and associate approach
                media = CogniacMedia.create(
                    cc,
                    filename=file_path,
                    meta_tags=meta_tags,
                    force_set='training'
                )
                subject.associate_media(media)
                
            except Exception as e1:
                try:
                    # Method 2: Try creating media with different parameters
                    media = CogniacMedia.create(
                        cc,
                        filename=file_path,
                        meta_tags=meta_tags
                    )
                    subject.associate_media(media)
                    
                except Exception as e2:
                    try:
                        # Method 3: Try uploading directly through connection
                        with open(file_path, 'rb') as f:
                            media = cc.upload_media(
                                f,
                                filename=filename,
                                meta_tags=meta_tags,
                                subject_uid=subject.subject_uid
                            )
                    except Exception as e3:
                        raise Exception(f"All upload methods failed. Last error: {str(e3)}")
            
            return {
                'status': 'success',
                'filename': filename,
                'media_id': media.media_id
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'filename': filename,
                'error': str(e)
            }
    
    def process_folder_batch():
        """Process folder batch upload in background"""
        successful_uploads = []
        failed_uploads = []
        
        # Use ThreadPoolExecutor for parallel uploads
        max_workers = min(10, len(image_files))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(upload_single_image_from_path, file_path, meta_tags, batch_id): file_path
                for file_path in image_files
            }
            
            # Process completed uploads
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    
                    if result['status'] == 'success':
                        successful_uploads.append(result)
                        upload_progress[batch_id]['successful'] += 1
                    else:
                        failed_uploads.append(result)
                        upload_progress[batch_id]['failed'] += 1
                    
                    upload_progress[batch_id]['completed'] += 1
                    upload_progress[batch_id]['results'].append(result)
                    
                except Exception as e:
                    failed_uploads.append({
                        'status': 'error',
                        'filename': os.path.basename(file_path),
                        'error': str(e)
                    })
                    upload_progress[batch_id]['failed'] += 1
                    upload_progress[batch_id]['completed'] += 1
        
        # Update final status
        upload_progress[batch_id]['status'] = 'completed'
    
    # Start batch processing in background
    thread = threading.Thread(target=process_folder_batch)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'batch_id': batch_id,
        'total_files': len(image_files),
        'status': 'processing',
        'folder_path': folder_path,
        'message': f'Folder batch upload started for {len(image_files)} images. Use /batch-status/{batch_id} to check progress.'
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'subject_uid': subject.subject_uid,
        'connection': 'active'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)