import customtkinter as ctk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import pytesseract
from customtkinter import CTkImage
from fpdf import FPDF
import numpy as np
import os
import boto3
from botocore.exceptions import NoCredentialsError

# Initialize Tesseract OCR Path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# AWS S3 Configuration (Update with your credentials)
AWS_ACCESS_KEY = 'YOUR_AWS_ACCESS_KEY'
AWS_SECRET_KEY = 'YOUR_AWS_SECRET_KEY'
AWS_BUCKET_NAME = 'YOUR_BUCKET_NAME'
AWS_REGION = 'YOUR_REGION'


class IntelligentCamScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI-Powered CamScanner")
        self.geometry("1000x700")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.image = None # ID for the image on the canvas
        self.processed_image = None
        self.pdf_images = []
        self.zoom_level = 1.0  # Initialize zoom level
        self.init_ui()

    def init_ui(self):
        # Left Frame: Controls
        self.control_frame = ctk.CTkFrame(self, width=200, corner_radius=10)
        self.control_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.upload_button = ctk.CTkButton(self.control_frame, text="Upload Image", command=self.upload_image)
        self.upload_button.pack(pady=10)

        self.process_button = ctk.CTkButton(self.control_frame, text="Process Image", command=self.process_image)
        self.process_button.pack(pady=10)

        self.add_page_button = ctk.CTkButton(self.control_frame, text="Add to PDF", command=self.add_to_pdf)
        self.add_page_button.pack(pady=10)

        self.extract_text_button = ctk.CTkButton(self.control_frame, text="Extract Text", command=self.extract_text)
        self.extract_text_button.pack(pady=10)

        self.export_pdf_button = ctk.CTkButton(self.control_frame, text="Export to PDF", command=self.export_to_pdf)
        self.export_pdf_button.pack(pady=10)

        self.upload_to_cloud_button = ctk.CTkButton(self.control_frame, text="Upload to Cloud",
                                                    command=self.upload_to_cloud)
        self.upload_to_cloud_button.pack(pady=10)

        self.filter_label = ctk.CTkLabel(self.control_frame, text="Image Filters")
        self.filter_label.pack(pady=10)

        self.grayscale_button = ctk.CTkButton(self.control_frame, text="Grayscale",
                                              command=lambda: self.apply_filter("grayscale"))
        self.grayscale_button.pack(pady=5)

        self.binarize_button = ctk.CTkButton(self.control_frame, text="Binarize",
                                             command=lambda: self.apply_filter("binarize"))
        self.binarize_button.pack(pady=5)

        self.brightness_button = ctk.CTkButton(self.control_frame, text="Brightness +",
                                               command=lambda: self.apply_filter("brightness"))
        self.brightness_button.pack(pady=5)

        self.reset_button = ctk.CTkButton(self.control_frame, text="Reset", command=self.reset_image)
        self.reset_button.pack(pady=10)

        # Landscape and Portrait Switch Buttons
        self.landscape_button = ctk.CTkButton(self.control_frame, text="Switch to Landscape",
                                              command=self.switch_to_landscape)
        self.landscape_button.pack(pady=10)

        self.portrait_button = ctk.CTkButton(self.control_frame, text="Switch to Portrait",
                                             command=self.switch_to_portrait)
        self.portrait_button.pack(pady=10)

        # Right Frame: Image Display
        self.image_frame = ctk.CTkFrame(self, corner_radius=10)
        self.image_frame.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        self.canvas = ctk.CTkCanvas(self.image_frame, bg="gray")
        self.canvas.pack(fill="both", expand=True)


        # Bind mouse events for moving the image
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.move_image)


        # Zoom In and Zoom Out Buttons as Images
        self.zoom_in_icon = CTkImage(light_image=Image.open("in.png"),
                                  dark_image=Image.open("in.png"), size=(40, 40))
        self.zoom_out_icon = CTkImage(light_image=Image.open("out.png"),
                                 dark_image=Image.open("out.png"), size=(40, 40))

        # Zoom-in icon - clickable image
        self.zoom_in_label = ctk.CTkLabel(self.canvas, image=self.zoom_in_icon, text="")
        self.zoom_in_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-30)  # Position at the bottom-right
        self.zoom_in_label.bind("<Button-1>", lambda event: self.zoom_in())  # Bind left mouse click to zoom_in function

        # Zoom-out icon - clickable image
        self.zoom_out_label = ctk.CTkLabel(self.canvas, image=self.zoom_out_icon, text="")
        self.zoom_out_label.place(relx=1.0, rely=1.0, anchor="se", x=-80,
                                  y=-30)  # Position to the left of the zoom-in icon
        self.zoom_out_label.bind("<Button-1>",
                                 lambda event: self.zoom_out())  # Bind left mouse click to zoom_out function

    def switch_to_landscape(self):
        if self.image is not None:
            height, width = self.image.shape[:2]
            if width < height:  # If the image is in portrait, rotate it
                self.image = cv2.rotate(self.image, cv2.ROTATE_90_CLOCKWISE)
                self.display_image(self.image)
            else:
                messagebox.showinfo("Info", "Image is already in landscape mode.")
        else:
            messagebox.showerror("Error", "Please upload an image first.")

    def switch_to_portrait(self):
        if self.image is not None:
            height, width = self.image.shape[:2]
            if width > height:  # If the image is in landscape, rotate it
                self.image = cv2.rotate(self.image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                self.display_image(self.image)
            else:
                messagebox.showinfo("Info", "Image is already in portrait mode.")
        else:
            messagebox.showerror("Error", "Please upload an image first.")

    def start_move(self, event):
        # Store the initial mouse click position
        self.start_x = event.x
        self.start_y = event.y

    def move_image(self, event):
        # Calculate the movement offset
        dx = event.x - self.start_x
        dy = event.y - self.start_y

        # Update the position and redraw the image
        self.canvas.move(self.image, dx, dy)
        self.start_x = event.x
        self.start_y = event.y

    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            self.image = cv2.imread(file_path)
            self.display_image(self.image)

    def process_image(self):
        if self.image is not None:
            gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 50, 150)

            contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            for contour in contours:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:
                    self.processed_image = self.four_point_transform(self.image, approx.reshape(4, 2))
                    break

            if self.processed_image is not None:
                self.display_image(self.processed_image)
            else:
                messagebox.showerror("Error", "Could not detect document boundaries.")
        else:
            messagebox.showerror("Error", "Please upload an image first.")
    def four_point_transform(self, image, pts):
        rect = np.array(pts, dtype="float32")
        (tl, tr, br, bl) = rect

        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype="float32")

        matrix = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, matrix, (max_width, max_height))
    def add_to_pdf(self):
        if self.processed_image is not None:
            temp_image_path = "temp_image.jpg"
            cv2.imwrite(temp_image_path, self.processed_image)
            self.pdf_images.append(temp_image_path)
            messagebox.showinfo("Success", "Image added to PDF.")
        else:
            messagebox.showerror("Error", "No processed image available to add.")

    def extract_text(self):
        if self.processed_image is not None:
            gray = cv2.cvtColor(self.processed_image, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray)
            messagebox.showinfo("Extracted Text", text)
        else:
            messagebox.showerror("Error", "No processed image available for text extraction.")

    def export_to_pdf(self):
        if self.pdf_images:
            pdf = FPDF()
            for img_path in self.pdf_images:
                pdf.add_page()
                pdf.image(img_path, x=10, y=10, w=190)
            output_file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
            if output_file:
                pdf.output(output_file)
                for img_path in self.pdf_images:
                    os.remove(img_path)
                self.pdf_images.clear()
                messagebox.showinfo("Success", "PDF exported successfully.")
        else:
            messagebox.showerror("Error", "No images added to PDF.")

    def upload_to_cloud(self):
        if self.pdf_images:
            s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY,
                                     region_name=AWS_REGION)
            output_file = "scanned_document.pdf"
            self.export_to_pdf()  # Create the PDF locally first
            try:
                s3_client.upload_file(output_file, AWS_BUCKET_NAME, output_file)
                os.remove(output_file)  # Remove local file after upload
                messagebox.showinfo("Success", "PDF uploaded to cloud storage.")
            except NoCredentialsError:
                messagebox.showerror("Error", "AWS Credentials not configured properly.")
        else:
            messagebox.showerror("Error", "No images available for upload.")

    def apply_filter(self, filter_type):
        if self.image is not None:
            if filter_type == "grayscale":
                self.processed_image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            elif filter_type == "binarize":
                _, self.processed_image = cv2.threshold(self.image, 127, 255, cv2.THRESH_BINARY)
            elif filter_type == "brightness":
                self.processed_image = cv2.convertScaleAbs(self.image, alpha=1.2, beta=50)  # Adjust brightness
            self.display_image(self.processed_image)  # To display the modified image
        else:
            messagebox.showerror("Error", "Please upload an image first.")

    def reset_image(self):
        if self.image is not None:
            self.display_image(self.image)
        else:
            messagebox.showerror("Error", "No image to reset.")

    def display_image(self, image):
        if len(image.shape) == 2:  # Grayscale image
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_resized = cv2.resize(image_rgb, None, fx=self.zoom_level, fy=self.zoom_level)
        image_pil = Image.fromarray(image_resized)
        image_tk = ImageTk.PhotoImage(image_pil)
        self.canvas.create_image(0, 0, anchor="nw", image=image_tk)
        self.canvas.image = image_tk

    def zoom_in(self):
        if self.processed_image is not None:
            self.zoom_level *= 1.2  # Increase zoom factor
            self.display_image(self.processed_image)

    def zoom_out(self):
        if self.processed_image is not None:
            self.zoom_level /= 1.2  # Decrease zoom factor
            self.display_image(self.processed_image)

if __name__ == "__main__":
    app = IntelligentCamScannerApp()
    app.mainloop()
