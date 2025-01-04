# Additional tools

## Convert the label files to CSV

### Introduction
To train the images on [Google Cloud AutoML](https://cloud.google.com/automl), we should prepare the specific csv files follow [this format](https://cloud.google.com/vision/automl/object-detection/docs/csv-format).

`label_to_csv.py` can convert the `txt` or `xml` label files to csv file. The labels files should strictly follow to below structure.

### Structures
* Images
    To train the object detection tasks, all the images should upload to the cloud storage and access it by its name. All the images should stay in the **same buckets** in cloud storage. Also, different classes should have their own folder as below.
    ```
    <bucket_name> (on the cloud storage)
    | -- class1
    |    | -- class1_01.jpg
    |    | -- class1_02.jpg
    |    | ...
    | -- class2
    |    | -- class2_01.jpg
    |    | -- class2_02.jpg
    |    | ...
    | ...
    ```
    Note, URI of the `class1_01.jpg` is `gs://<bucket_name>/class1/class1_01.jpg`
* Labels
    There are four types of training data - `TRAINING`, `VALIDATION`, `TEST` and `UNASSIGNED`. To assign different categories, we should create four directories.
    Inside each folder, users should create the class folders with the same name in cloud storage (see below structure).
    ```
    labels (on PC)
    | -- TRAINING
    |    | -- class1
    |    |    | -- class1_01.txt (or .xml)
    |    |    | ...
    |    | -- class2
    |    |    | -- class2_01.txt (or .xml)
    |    |    | ...
    |    | ...
    | -- VALIDATION
    |    | -- class1
    |    |    | -- class1_02.txt (or .xml)
    |    |    | ...
    |    | -- class2
    |    |    | -- class2_02.txt (or .xml)
    |    |    | ...
    |    | ...
    | -- TEST
    |    | (same as TRAINING and VALIDATION)
    | -- UNASSIGNED
    |    | (same as TRAINING and VALIDATION)
    ```

### Usage

To see the argument of `label_to_csv.py`,
```commandline
python label_to_csv.py -h
```

```commandline
usage: label_to_csv.py [-h] -p PREFIX -l LOCATION -m MODE [-o OUTPUT]
                       [-c CLASSES]

optional arguments:
  -h, --help            show this help message and exit
  -p PREFIX, --prefix PREFIX
                        Bucket of the cloud storage path
  -l LOCATION, --location LOCATION
                        Parent directory of the label files
  -m MODE, --mode MODE  'xml' for converting from xml and 'txt' for converting
                        from txt
  -o OUTPUT, --output OUTPUT
                        Output name of csv file
  -c CLASSES, --classes CLASSES
                        Label classes path
```

For example, if mine bucket name is **test**, the location of the label directory is **/User/test/labels**, the mode I choose from is **txt**, the output name and the class path is same as default.
```commandline
python label_to_csv.py \
-p test\
-l /User/test/labels \
-m txt
```

The output file is `res.csv` by default. Afterwards, upload the csv file to the cloud storage and you can start training!

## Yolo_renamer_for_image_and_labels.py

### Image and Label Renamer
This Python script allows users to rename image files and their corresponding label files in specified directories. It utilizes the Tkinter library for a graphical interface to select directories and prompts the user for a new naming convention.
* Features
    Select directories for images and labels using a graphical file dialog.
    Automatically find matching files based on their names (excluding extensions).
    Rename both image and label files according to a specified new name with an index.

* Requirements
	Python 3.x
    Tkinter (included with standard Python installations)
    No additional libraries required

* Usage
    Run the script in a Python environment.
    Select the folders containing your images and labels when prompted.
    Enter a new base name for your files when prompted.
    The script will rename matching files accordingly.
