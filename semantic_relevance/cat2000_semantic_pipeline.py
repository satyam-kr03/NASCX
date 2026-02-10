#!/usr/bin/env python3
"""
CAT2000 Semantic Importance Estimation Pipeline
Quick implementation for XR semantic communication research
"""

import numpy as np
import cv2
from pathlib import Path
import matplotlib.pyplot as plt
from scipy.io import loadmat
import pandas as pd
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Install if needed: pip install ultralytics transformers torch torchvision tqdm scipy pillow

class CAT2000Loader:
    """Load CAT2000 dataset from your directory structure"""
    
    def __init__(self, base_path):
        """
        Args:
            base_path: Path to trainSet folder (e.g., '~/Projects/NASCX/data/saliency/CAT2000/trainSet')
        """
        self.base_path = Path(base_path)
        self.stimuli_path = self.base_path / 'Stimuli'
        self.fixmap_path = self.base_path / 'FIXATIONMAPS'
        self.fixloc_path = self.base_path / 'FIXATIONLOCS'
        
        self.categories = [
            'Action', 'Affective', 'Art', 'BlackWhite', 'Cartoon',
            'Fractal', 'Indoor', 'Inverted', 'Jumbled', 'LineDrawing',
            'LowResolution', 'Noisy', 'Object', 'OutdoorManMade',
            'OutdoorNatural', 'Pattern', 'Random', 'Satelite', 'Sketch', 'Social'
        ]
        
        print(f"✓ Dataset path: {self.base_path}")
        print(f"✓ Found {len(self.categories)} categories")
    
    def load_image(self, category, image_name):
        """Load stimulus image"""
        img_path = self.stimuli_path / category / f"{image_name}.jpg"
        
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")
        
        image = cv2.imread(str(img_path))
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    def load_fixation_map(self, category, image_name):
        """Load precomputed fixation map (ground truth)"""
        fixmap_path = self.fixmap_path / category / f"{image_name}.jpg"
        
        if not fixmap_path.exists():
            # Return zeros if not found
            return None
        
        fixmap = cv2.imread(str(fixmap_path), cv2.IMREAD_GRAYSCALE)
        fixmap = fixmap.astype(np.float32) / 255.0
        
        return fixmap
    
    def get_all_images_in_category(self, category):
        """Get list of all images in a category"""
        category_path = self.stimuli_path / category
        
        if not category_path.exists():
            return []
        
        images = list(category_path.glob('*.jpg'))
        return sorted([img.stem for img in images])
    
    def iterate_dataset(self, categories=None, max_per_category=None):
        """
        Iterator over dataset
        
        Args:
            categories: List of categories (None = all)
            max_per_category: Max images per category (None = all)
        """
        if categories is None:
            categories = self.categories
        
        total_images = 0
        for category in categories:
            if category not in self.categories:
                print(f"Warning: Category '{category}' not found")
                continue
                
            image_names = self.get_all_images_in_category(category)
            
            if max_per_category:
                image_names = image_names[:max_per_category]
            
            total_images += len(image_names)
        
        print(f"✓ Processing {total_images} images from {len(categories)} categories")
        
        with tqdm(total=total_images, desc="Processing images") as pbar:
            for category in categories:
                image_names = self.get_all_images_in_category(category)
                
                if max_per_category:
                    image_names = image_names[:max_per_category]
                
                for image_name in image_names:
                    try:
                        # Load image
                        image = self.load_image(category, image_name)
                        
                        # Load ground truth fixation map
                        fixation_map = self.load_fixation_map(category, image_name)
                        
                        if fixation_map is None:
                            # Create dummy if not found
                            fixation_map = np.zeros(image.shape[:2], dtype=np.float32)
                        
                        yield {
                            'image': image,
                            'fixation_map': fixation_map,
                            'category': category,
                            'image_name': image_name,
                            'shape': image.shape
                        }
                        
                        pbar.update(1)
                        
                    except Exception as e:
                        print(f"\nError processing {category}/{image_name}: {e}")
                        pbar.update(1)
                        continue


class SemanticImportanceEstimator:
    """Estimate semantic importance using pretrained models"""
    
    def __init__(self, device='cuda'):
        import torch
        self.device = device if torch.cuda.is_available() else 'cpu'
        print(f"\n🔄 Loading pretrained models (device: {self.device})...")
        
        # 1. Object Detection (YOLOv8)
        try:
            from ultralytics import YOLO
            self.object_detector = YOLO('yolov8n.pt')
            print("✓ YOLOv8 loaded")
        except Exception as e:
            print(f"⚠ YOLOv8 failed: {e}")
            self.object_detector = None
        
        # 2. Face Detection (OpenCV DNN)
        try:
            # Use OpenCV's DNN face detector (no extra dependencies)
            self.face_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            print("✓ Face detector loaded (Haar Cascade)")
        except Exception as e:
            print(f"⚠ Face detector failed: {e}")
            self.face_detector = None
        
        # 3. Deep Saliency Model - try TranSalNet or fallback to spectral residual
        self.saliency_model = None
        self.saliency_type = None
        
        try:
            # Try loading a pretrained saliency model via timm/transformers
            from transformers import CLIPProcessor, CLIPModel
            import torch
            
            # Use CLIP for attention-based saliency (works well for semantic importance)
            # Important: Use attn_implementation="eager" to support output_attentions=True
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
            self.clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-base-patch16",
                attn_implementation="eager"  # Required for output_attentions
            ).to(self.device)
            self.clip_model.eval()
            self.saliency_type = 'clip_attention'
            print("✓ CLIP attention saliency loaded (eager attention)")
        except Exception as e:
            print(f"⚠ CLIP saliency failed: {e}, using spectral residual fallback")
            # Fallback to OpenCV's spectral residual saliency
            try:
                self.saliency_model = cv2.saliency.StaticSaliencySpectralResidual_create()
                self.saliency_type = 'spectral_residual'
                print("✓ Spectral Residual saliency loaded")
            except Exception as e2:
                print(f"⚠ Spectral residual failed: {e2}, using fine-tuned center bias")
                self.saliency_type = 'center_bias'
        
        print("✓ All models loaded\n")
    
    def predict_saliency(self, image):
        """Deep learning-based saliency prediction with fallbacks"""
        h, w = image.shape[:2]
        
        if self.saliency_type == 'clip_attention':
            return self._clip_attention_saliency(image)
        elif self.saliency_type == 'spectral_residual':
            return self._spectral_residual_saliency(image)
        else:
            # Refined center bias - smaller sigma for tighter focus
            return self._refined_center_bias(image)
    
    def _clip_attention_saliency(self, image):
        """Extract attention maps from CLIP vision transformer"""
        import torch
        from PIL import Image
        
        h, w = image.shape[:2]
        
        try:
            # Prepare image for CLIP
            pil_image = Image.fromarray(image)
            inputs = self.clip_processor(images=pil_image, return_tensors="pt")
            pixel_values = inputs['pixel_values'].to(self.device)
            
            with torch.no_grad():
                # Get vision model outputs with attention
                # Access the vision_model directly from CLIPModel
                vision_outputs = self.clip_model.vision_model(
                    pixel_values=pixel_values,
                    output_attentions=True
                )
                
                # Check if attentions are available
                if vision_outputs.attentions is None or len(vision_outputs.attentions) == 0:
                    print("CLIP attention: attentions not available, using fallback")
                    return self._refined_center_bias(image)
                
                # Extract attention from last layer, average across heads
                # Shape: (batch, heads, seq_len, seq_len)
                attentions = vision_outputs.attentions[-1]
                
                # Get CLS token attention to all patches
                # Average across heads, take CLS attention (first token)
                cls_attention = attentions[0, :, 0, 1:].mean(dim=0)  # Exclude CLS itself
                
                # Reshape to 2D (CLIP uses 14x14 patches for 224x224 input with patch size 16)
                num_patches = int(cls_attention.shape[0] ** 0.5)
                if num_patches * num_patches != cls_attention.shape[0]:
                    # Handle case where it's not a perfect square
                    num_patches = 14  # Default for CLIP ViT-B/16
                
                attention_map = cls_attention.reshape(num_patches, num_patches).cpu().numpy()
                
                # Resize to original image size
                saliency = cv2.resize(attention_map, (w, h), interpolation=cv2.INTER_CUBIC)
                
                # Normalize
                saliency = (saliency - saliency.min()) / (saliency.max() - saliency.min() + 1e-8)
                
                # Apply slight Gaussian smoothing
                saliency = cv2.GaussianBlur(saliency.astype(np.float32), (15, 15), 0)
                
                # Blend with mild center bias (humans tend to look at center)
                # This combines CLIP's semantic understanding with known fixation patterns
                center_bias = self._refined_center_bias(image)
                saliency = 0.5 * saliency + 0.5 * center_bias
                
                # Re-normalize
                saliency = (saliency - saliency.min()) / (saliency.max() - saliency.min() + 1e-8)
                
                return saliency
                
        except Exception as e:
            print(f"CLIP attention error: {e}")
            return self._refined_center_bias(image)
    
    def _spectral_residual_saliency(self, image):
        """OpenCV Spectral Residual saliency"""
        h, w = image.shape[:2]
        
        try:
            success, saliency = self.saliency_model.computeSaliency(image)
            if success:
                saliency = saliency.astype(np.float32)
                saliency = (saliency - saliency.min()) / (saliency.max() - saliency.min() + 1e-8)
                # Smooth the result
                saliency = cv2.GaussianBlur(saliency, (11, 11), 0)
                return saliency
        except Exception as e:
            print(f"Spectral residual error: {e}")
        
        return self._refined_center_bias(image)
    
    def _refined_center_bias(self, image):
        """Refined center bias with tighter focus"""
        h, w = image.shape[:2]
        
        y, x = np.ogrid[:h, :w]
        center_y, center_x = h // 2, w // 2
        
        # Tighter sigma for less spread
        sigma_y = h / 4
        sigma_x = w / 4
        
        saliency = np.exp(-((x - center_x)**2 / (2 * sigma_x**2) + 
                           (y - center_y)**2 / (2 * sigma_y**2)))
        
        return saliency / (saliency.max() + 1e-8)
    
    def detect_faces(self, image):
        """Face detection importance - humans focus on faces"""
        if self.face_detector is None:
            return np.zeros(image.shape[:2], dtype=np.float32)
        
        h, w = image.shape[:2]
        importance_map = np.zeros((h, w), dtype=np.float32)
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            faces = self.face_detector.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            for (x, y, fw, fh) in faces:
                # Faces get very high importance
                # Create Gaussian centered on face
                face_center_x = x + fw // 2
                face_center_y = y + fh // 2
                
                yy, xx = np.ogrid[:h, :w]
                sigma = max(fw, fh) / 2
                
                face_gaussian = np.exp(-((xx - face_center_x)**2 + (yy - face_center_y)**2) / (2 * sigma**2))
                face_gaussian = face_gaussian / (face_gaussian.max() + 1e-8)
                
                importance_map = np.maximum(importance_map, face_gaussian * 0.95)
                
        except Exception as e:
            print(f"Face detection error: {e}")
        
        return importance_map
    
    def detect_objects(self, image):
        """Object detection importance with refined weighting"""
        if self.object_detector is None:
            return np.zeros(image.shape[:2], dtype=np.float32)
        
        h, w = image.shape[:2]
        importance_map = np.zeros((h, w), dtype=np.float32)
        
        try:
            results = self.object_detector(image, verbose=False)
            
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        confidence = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # Clip to image bounds
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w, x2), min(h, y2)
                        
                        if x2 <= x1 or y2 <= y1:
                            continue
                        
                        # Create Gaussian blob instead of flat rectangle
                        obj_importance = self._get_object_importance(class_id, confidence)
                        
                        # Create soft mask with Gaussian falloff
                        box_h, box_w = y2 - y1, x2 - x1
                        center_y, center_x = (y1 + y2) // 2, (x1 + x2) // 2
                        
                        yy, xx = np.ogrid[:h, :w]
                        sigma_y = box_h / 2.5
                        sigma_x = box_w / 2.5
                        
                        obj_gaussian = np.exp(-((xx - center_x)**2 / (2 * sigma_x**2 + 1e-8) + 
                                                (yy - center_y)**2 / (2 * sigma_y**2 + 1e-8)))
                        obj_gaussian = obj_gaussian * obj_importance
                        
                        importance_map = np.maximum(importance_map, obj_gaussian)
                        
        except Exception as e:
            print(f"Object detection error: {e}")
        
        return importance_map
    
    def _get_object_importance(self, class_id, confidence):
        """Class-specific importance weights (refined)"""
        # COCO classes: person=0, vehicles=2-7, animals=14-23
        very_high = [0]  # Person
        high_importance = [1, 2, 3, 5, 7]  # Vehicles
        medium_high = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]  # Animals
        
        if class_id in very_high:
            return 0.9 * confidence
        elif class_id in high_importance:
            return 0.75 * confidence
        elif class_id in medium_high:
            return 0.7 * confidence
        else:
            return 0.5 * confidence
    
    def compute_texture_importance(self, image):
        """Edge/texture-based importance (refined with lower weight on uniform textures)"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Sobel edge detection
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        
        # Suppress uniform/repetitive textures by local variance thresholding
        local_var = cv2.blur(magnitude**2, (31, 31)) - cv2.blur(magnitude, (31, 31))**2
        texture_mask = local_var > np.percentile(local_var, 50)
        
        magnitude = magnitude * texture_mask.astype(np.float32)
        magnitude = magnitude / (magnitude.max() + 1e-8)
        
        # Smooth
        magnitude = cv2.GaussianBlur(magnitude.astype(np.float32), (7, 7), 0)
        
        return magnitude
    
    def estimate(self, image, category='general'):
        """
        Main estimation function
        
        Returns:
            importance_map: Combined semantic importance
            components: Individual component maps
        """
        # 1. Deep saliency prediction
        saliency = self.predict_saliency(image)
        
        # 2. Face detection (high priority for human attention)
        faces = self.detect_faces(image)
        
        # 3. Object detection
        objects = self.detect_objects(image)
        
        # 4. Texture/edges
        texture = self.compute_texture_importance(image)
        
        # 5. Category-specific fusion weights
        weights = self._get_category_weights(category)
        
        # 6. Weighted combination with face priority
        importance_map = (
            weights['saliency'] * saliency +
            weights['face'] * faces +
            weights['object'] * objects +
            weights['texture'] * texture
        )
        
        # Normalize to [0, 1]
        importance_map = importance_map / (importance_map.max() + 1e-8)
        importance_map = np.clip(importance_map, 0, 1)
        
        components = {
            'saliency': saliency,
            'face': faces,
            'object': objects,
            'texture': texture,
            'category': category,
            'weights': weights
        }
        
        return importance_map, components
    
    def _get_category_weights(self, category):
        """Category-aware weight assignment (rebalanced for better accuracy)"""
        # Reduced saliency weight, increased object/face weight
        if category in ['Action', 'Social']:
            # People-focused: prioritize faces and objects
            return {'saliency': 0.15, 'face': 0.40, 'object': 0.40, 'texture': 0.05}
        elif category in ['Art', 'Pattern', 'Fractal']:
            # Texture-focused
            return {'saliency': 0.25, 'face': 0.10, 'object': 0.15, 'texture': 0.50}
        elif category in ['Object', 'Indoor', 'OutdoorManMade', 'OutdoorNatural']:
            # Object-focused
            return {'saliency': 0.20, 'face': 0.25, 'object': 0.45, 'texture': 0.10}
        elif category in ['Cartoon', 'Sketch', 'LineDrawing']:
            # Character/drawing focused
            return {'saliency': 0.20, 'face': 0.35, 'object': 0.30, 'texture': 0.15}
        else:
            # Default balanced
            return {'saliency': 0.20, 'face': 0.30, 'object': 0.35, 'texture': 0.15}


def visualize_results(data, importance_map, components, save_path):
    """Create comprehensive visualization with face detection"""
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # Row 1: Original, Ground Truth, Saliency
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.imshow(data['image'])
    ax1.set_title('Original Image', fontsize=12, fontweight='bold')
    ax1.axis('off')
    
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(data['fixation_map'], cmap='hot')
    ax2.set_title('Ground Truth Gaze\n(Human Fixations)', fontsize=12, fontweight='bold')
    ax2.axis('off')
    
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.imshow(components['saliency'], cmap='hot')
    ax3.set_title('Saliency (Deep/CLIP)', fontsize=12)
    ax3.axis('off')
    
    # Row 2: Face Detection, Object Detection, Texture
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.imshow(components.get('face', np.zeros_like(components['saliency'])), cmap='hot')
    ax4.set_title('Face Detection', fontsize=12)
    ax4.axis('off')
    
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.imshow(components['object'], cmap='hot')
    ax5.set_title('Object Detection', fontsize=12)
    ax5.axis('off')
    
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.imshow(components['texture'], cmap='hot')
    ax6.set_title('Texture/Edges', fontsize=12)
    ax6.axis('off')
    
    # Row 3: Combined, Overlay, Correlation
    ax7 = fig.add_subplot(gs[2, 0])
    ax7.imshow(importance_map, cmap='hot')
    ax7.set_title('Combined Importance\n(Predicted)', fontsize=12, fontweight='bold')
    ax7.axis('off')
    
    ax8 = fig.add_subplot(gs[2, 1])
    overlay = data['image'].copy().astype(np.float32) / 255.0
    heatmap_colored = plt.cm.hot(importance_map)[:, :, :3]
    overlay = (0.6 * overlay + 0.4 * heatmap_colored)
    ax8.imshow(overlay)
    ax8.set_title('Overlay (Prediction)', fontsize=12)
    ax8.axis('off')
    
    # Correlation plot
    ax9 = fig.add_subplot(gs[2, 2])
    gt_flat = data['fixation_map'].flatten()
    pred_flat = importance_map.flatten()
    
    # Compute correlation
    correlation = np.corrcoef(gt_flat, pred_flat)[0, 1]
    
    ax9.scatter(gt_flat, pred_flat, alpha=0.1, s=1)
    ax9.set_xlabel('Ground Truth')
    ax9.set_ylabel('Predicted')
    ax9.set_title(f'Correlation: {correlation:.3f}', fontsize=12)
    ax9.grid(True, alpha=0.3)
    
    # Add metadata with all four weights
    face_weight = components['weights'].get('face', 0)
    fig.suptitle(
        f"Category: {data['category']} | Image: {data['image_name']} | "
        f"Weights - S:{components['weights']['saliency']:.2f} "
        f"F:{face_weight:.2f} "
        f"O:{components['weights']['object']:.2f} "
        f"T:{components['weights']['texture']:.2f}",
        fontsize=14, fontweight='bold'
    )
    
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def run_pipeline(dataset_path, output_path, categories=None, max_per_category=10):
    """
    Main pipeline execution
    
    Args:
        dataset_path: Path to CAT2000/trainSet
        output_path: Output directory
        categories: List of categories to process
        max_per_category: Images per category
    """
    print("="*70)
    print("CAT2000 Semantic Importance Estimation Pipeline")
    print("="*70)
    
    # Initialize
    loader = CAT2000Loader(dataset_path)
    estimator = SemanticImportanceEstimator()
    
    output_path = Path(output_path)
    output_path.mkdir(exist_ok=True, parents=True)
    
    # Create subdirectories
    (output_path / 'importance_maps').mkdir(exist_ok=True)
    (output_path / 'visualizations').mkdir(exist_ok=True)
    
    results = []
    
    # Process dataset
    for data in loader.iterate_dataset(categories, max_per_category):
        # Estimate importance
        importance_map, components = estimator.estimate(
            data['image'],
            data['category']
        )
        
        # Save importance map
        save_dir = output_path / 'importance_maps' / data['category']
        save_dir.mkdir(parents=True, exist_ok=True)
        np.save(save_dir / f"{data['image_name']}.npy", importance_map)
        
        # Visualize
        vis_dir = output_path / 'visualizations' / data['category']
        vis_dir.mkdir(parents=True, exist_ok=True)
        visualize_results(
            data,
            importance_map,
            components,
            vis_dir / f"{data['image_name']}.png"
        )
        
        # Compute metrics
        correlation = np.corrcoef(
            data['fixation_map'].flatten(),
            importance_map.flatten()
        )[0, 1]
        
        # KL divergence (for saliency comparison)
        eps = 1e-8
        gt_norm = data['fixation_map'] / (data['fixation_map'].sum() + eps)
        pred_norm = importance_map / (importance_map.sum() + eps)
        kl_div = np.sum(gt_norm * np.log((gt_norm + eps) / (pred_norm + eps)))
        
        results.append({
            'category': data['category'],
            'image_name': data['image_name'],
            'correlation': correlation,
            'kl_divergence': kl_div,
            'mean_importance': importance_map.mean(),
            'max_importance': importance_map.max(),
            'weight_saliency': components['weights']['saliency'],
            'weight_object': components['weights']['object'],
            'weight_texture': components['weights']['texture']
        })
    
    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_path / 'results.csv', index=False)
    
    # Print summary
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print(f"\nTotal images processed: {len(results_df)}")
    print(f"\nCorrelation with Ground Truth Gaze:")
    print(f"  Mean: {results_df['correlation'].mean():.3f}")
    print(f"  Std:  {results_df['correlation'].std():.3f}")
    print(f"  Min:  {results_df['correlation'].min():.3f}")
    print(f"  Max:  {results_df['correlation'].max():.3f}")
    
    print(f"\nKL Divergence (lower is better):")
    print(f"  Mean: {results_df['kl_divergence'].mean():.3f}")
    print(f"  Std:  {results_df['kl_divergence'].std():.3f}")
    
    print(f"\nPer-Category Performance:")
    category_stats = results_df.groupby('category')['correlation'].agg(['mean', 'std', 'count'])
    print(category_stats.to_string())
    
    print(f"\n✓ Results saved to: {output_path}/results.csv")
    print(f"✓ Visualizations saved to: {output_path}/visualizations/")
    print("="*70)
    
    return results_df


if __name__ == '__main__':
    # Configuration
    DATASET_PATH = '~/Projects/NASCX/data/saliency/CAT2000/trainSet'
    OUTPUT_PATH = './cat2000_output'
    
    # Expand home directory
    DATASET_PATH = Path(DATASET_PATH).expanduser()
    
    # Quick test with subset
    CATEGORIES = ['Action', 'Social', 'Object', 'Indoor']  # Start with these
    MAX_PER_CATEGORY = 10  # 10 images per category = 40 total
    
    # Run pipeline
    results = run_pipeline(
        dataset_path=DATASET_PATH,
        output_path=OUTPUT_PATH,
        categories=CATEGORIES,
        max_per_category=MAX_PER_CATEGORY
    )
    
    print("\n✅ Pipeline completed successfully!")
    print(f"📊 Check {OUTPUT_PATH}/visualizations/ for results")