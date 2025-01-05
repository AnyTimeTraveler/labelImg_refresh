About LabelImg
========
LabelImg is a graphical image annotation tool.

It is written in Python and uses Qt for its graphical interface.

Annotations are saved as XML files in PASCAL VOC format, the format used
by ImageNet.  Besides, it also supports YOLO and CreateML formats.

About Fork labelImg_refresh
========
The primary goal of this fork is to enhance the stability and performance of the program on modern systems, particularly with Python 3. This initiative aims to address and resolve existing issues that lead to crashes and bugs, ensuring a smoother user experience.

#### Improve Stability:
  * The fork focuses on making the application more robust and reliable when running on contemporary operating systems and environments.
#### Compatibility with Python 3.10+:
  * Given the advancements in Python 3, this fork will ensure that the program fully utilizes the features and improvements offered by this version of the language.
#### Bug Fixes:
  * Identify and rectify known bugs that may cause unexpected behavior or crashes during use. This includes thorough testing and debugging to ensure a more stable application.

Build from source
========
## Ubuntu Linux
### Python 3 + Qt5

```bash
    sudo apt-get install pyqt5-dev-tools
    sudo pip3 install -r requirements.txt
    make qt5py3
    python3 labelImg.py
    python3 labelImg.py [IMAGE_PATH] [PRE-DEFINED CLASS FILE]
```

## Windows

* Install Python https://www.python.org/downloads/windows/

```cmd
    pip install pyqt5 lxml
```
* Open cmd and go to the `labelImg <#labelimg>` directory

```cmd
    pyrcc5 resources.qrc -o resources.py
    pyrcc5 -o libs/resources.py resources.qrc

    python labelImg.py
    python labelImg.py [IMAGE_PATH] [PRE-DEFINED CLASS FILE]
```

* If you want to package it into a folder with EXE (portatable):
    * Install pyinstaller and execute:

```cmd
    pip install pyinstaller
    pyinstaller --hidden-import=pyqt5 --hidden-import=lxml -n "labelImg" -c labelImg.py -p ./ --add-data "./data/;./data" --add-data "./libs;./libs"
```
    * You can set the list of required classes in `labelImg\_internal\data\predefined_classes.txt `
    * The settings file is stored at `\labeling\_internal\lib\.label Img Settings.pl `

## Usage
### Steps (PascalVOC)
1. Build and launch using the instructions above.
2. Click 'Change default saved annotation folder' in Menu/File
3. Click 'Open Dir'
4. Click 'Create RectBox'
5. Click and release left mouse to select a region to annotate the rect
   box
6. You can use right mouse to drag the rect box to copy or move it

The annotation will be saved to the folder you specify.
You can refer to the below hotkeys to speed up your workflow.

### Steps (YOLO)

1. In ``data/predefined_classes.txt`` define the list of classes that will be used for your training.

2. Build and launch using the instructions above.

3. Right below "Save" button in the toolbar, click "PascalVOC" button to switch to YOLO format.

4. You may use Open/OpenDIR to process single or multiple images. When finished with a single image, click save.

A txt file of YOLO format will be saved in the same folder as your image with same name.
A file named `labels.txt` is saved to that folder too. `labels.txt` defines the list of class names that your YOLO label refers to.

## Create pre-defined classes
You can edit the `data/predefined_classes.txt` to load pre-defined classes

## Annotation visualization
1. Copy the existing lables file to same folder with the images. The labels file name must be same with image file name.
2. Click File and choose `Open Dir` then Open the image folder.
3. Select image in File List, it will appear the bounding box and label for all objects in that image.
4. (Choose Display Labels mode in View to show/hide lablels)


## Hotkeys
~~~~~~~
+--------------------+--------------------------------------------+
| Ctrl + u           | Load all of the images from a directory    |
+--------------------+--------------------------------------------+
| Ctrl + r           | Change the default annotation target dir   |
+--------------------+--------------------------------------------+
| Ctrl + s           | Save                                       |
+--------------------+--------------------------------------------+
| Ctrl + d           | Copy the current label and rect box        |
+--------------------+--------------------------------------------+
| Ctrl + Shift + d   | Delete the current image                   |
+--------------------+--------------------------------------------+
| Space              | Flag the current image as verified         |
+--------------------+--------------------------------------------+
| w                  | Create a rect box                          |
+--------------------+--------------------------------------------+
| d                  | Next image                                 |
+--------------------+--------------------------------------------+
| a                  | Previous image                             |
+--------------------+--------------------------------------------+
| del                | Delete the selected rect box               |
+--------------------+--------------------------------------------+
| Ctrl++             | Zoom in                                    |
+--------------------+--------------------------------------------+
| Ctrl--             | Zoom out                                   |
+--------------------+--------------------------------------------+
| ↑→↓←               | Keyboard arrows to move selected rect box  |
+--------------------+--------------------------------------------+
~~~~~~~
**Verify Image:**

When pressing space, the user can flag the image as verified, a green background will appear.
This is used when creating a dataset automatically, the user can then through all the pictures and flag them instead of annotate them.

**Difficult:**

The difficult field is set to 1 indicates that the object has been annotated as "difficult", for example, an object which is clearly visible but difficult to recognize without substantial use of context.
According to your deep neural network implementation, you can include or exclude difficult objects during training.

### How to reset the settings
In case there are issues with loading the classes, you can either:
1. From the top menu of the labelimg click on **Menu/File/Reset All**
2. Remove the `.labelImgSettings.pkl` from `libs` directory in `labelImg_refresh`.

### License
Free software: MIT license

Original source citation: Tzutalin. LabelImg. Git code (2015) https://github.com/tzutalin/labelImg

Fork: SLY-F0X. labelImg_refresh. Git code (2025) https://github.com/SLY-F0X/labelImg_refresh
