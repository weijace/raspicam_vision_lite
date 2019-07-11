import sys
import logging
import cv2
import multiprocessing as mp


TOP_K = 5

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt=' %I:%M:%S ',
    level="INFO"
)
logger = logging.getLogger(__name__)

logger.info('Only top {} labels will be showed'.format(TOP_K))

def gen(camera, model):
    
    def get_inference(frame_in_queue, label_out_queue):
        
        def preds_to_text(preds, elapsed_time, top=TOP_K):
            top_indices = preds.argsort()[-top:][::-1]
            result = [(model.labels[i], preds[i]) for i in top_indices] # (labels, scores)
            result.sort(key=lambda x: x[1], reverse=True)
            result.insert(0, ('Elapsed time', elapsed_time))
            
            text = ''
            for item in result:
                s = '{}: {}\t'.format(*item)
                text += s
            return text
        
        
        while True:
            if not frame_in_queue.empty():
                frame = frame_in_queue.get()
                preds, elapsed_time = model.inference(frame)
                
                text = preds_to_text(preds, elapsed_time, TOP_K)
                label_out_queue.put(text)

    
    # Creates a child process dedicated for model inferencing
    frame_in_queue = mp.Queue(maxsize=1)
    label_out_queue = mp.Queue(maxsize=1)
    p = mp.Process(target=get_inference, args=(frame_in_queue, label_out_queue,), daemon=True)
    p.start()
    logger.info('Started a child process {} for inferencing.'.format(p.name))
    
    
    # Sets properties for label overlays on frames
    FONT_FACE = cv2.FONT_HERSHEY_PLAIN
    FONT_SCALE = 1
    FONT_COLOR = (255, 255, 255)
    THICKNESS = 1
    LINE_TYPE = cv2.LINE_AA
    REC_COLOR = (64, 64, 64)
    ALPHA = 0.6
    ANCHOR = (20, 20)
    (_, text_height), _ = cv2.getTextSize('test text', FONT_FACE, FONT_SCALE, THICKNESS)
    rectangle_shape = (260, text_height*(2*(TOP_K+2)+1))
    
    # Starts generating video frames indefinitely
    label_text_last = ''
    while True:
        frame = next(camera)
        overlay = frame.copy()
        
        # Sets the current frame onto frame_in_queue, if the input queue is empty
        if frame_in_queue.empty():
            frame_in_queue.put(frame)
            
        # Fetches the results from label_out_queue, if the output queue is not empty
        if not label_out_queue.empty():
            label_text = label_out_queue.get().split('\t')
            label_text_last = label_text
        
        # Draws label overlays
        if label_text_last:
            overlay = cv2.rectangle(overlay, ANCHOR, rectangle_shape, REC_COLOR, -1)
            for i, text in enumerate(label_text_last):
                text_pos = (ANCHOR[0]+text_height, ANCHOR[1]+2*(i+1)*text_height)
                overlay = cv2.putText(overlay, text, text_pos, FONT_FACE, FONT_SCALE, FONT_COLOR, THICKNESS, LINE_TYPE)
            overlay = cv2.addWeighted(frame, ALPHA, overlay, 1 - ALPHA, 0)
            
        # Encodes image into JPEG in order to correctly display the video stream.
        ret, overlay = cv2.imencode('.jpg', overlay) 
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + overlay.tobytes() + b'\r\n\r\n')



