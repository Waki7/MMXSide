import scipy.io
import os
from os.path import join, isfile
import numpy as np
import cv2
import pickle
import matplotlib.pyplot as plt
from scipy.io import loadmat


class DataSet():
    def __init__(self):
        self.file_ext = None
        self.root_path = None
        self.stored_data_path = None
        self.stored_file_name = None
        self.sampled_file_name = None
        self.paths = None
        self.downsample_ratio = 1

    def readFile(self, file):
        raise NotImplementedError

    def pad(self, image: np.ndarray, maxShape):
        pad_width = [(0, maxShape[i] - image.shape[i]) for i in range(len(maxShape))]
        return np.pad(image,
                      pad_width=pad_width, mode='constant')

    def saveData(self, path, filename, array):
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path + filename, 'wb') as f: pickle.dump(array, f)

    def loadArray(self, path, filename):
        with open(path + filename, 'rb') as f: return pickle.load(f)

    def processImages(self, directoryPath):
        data = []
        data_downsampled = []
        for filename in os.listdir(directoryPath):
            if filename.endswith(self.file_ext):
                samplePath = join(directoryPath, filename)
                image, image_downsampled = self.readFile(samplePath)
                if image.shape[0] > image.shape[1]:  # want all images to be in portrait
                    image = np.swapaxes(image, 0, 1)
                    image_downsampled = np.swapaxes(image_downsampled, 0, 1)
                data.append(image)
                data_downsampled.append(image_downsampled)
        return np.stack(data), np.stack(data_downsampled)

    def getData(self):
        data = []
        data_downsampled = []
        if isfile(self.stored_data_path + self.stored_file_name) and isfile(
                self.stored_data_path + self.sampled_file_name):
            data = self.loadArray(self.stored_data_path, self.stored_file_name)
            data_downsampled = self.loadArray(self.stored_data_path, self.sampled_file_name)
            print('...loaded arrays of shape ' + str(data.shape) +' and downsampled to '+ str(data_downsampled.shape))
            return data, data_downsampled
        for set in self.paths:
            processed = self.processImages(set)
            data.append(processed[0])
            data_downsampled.append(processed[1])
        data = np.vstack(data)
        data_downsampled = np.vstack(data_downsampled)
        self.saveData(self.stored_data_path, self.stored_file_name, data)
        self.saveData(self.stored_data_path, self.sampled_file_name, data_downsampled)
        return data, data_downsampled


class BSRLabels(DataSet):
    def __init__(self, downsampleRatio):
        super(BSRLabels, self).__init__()
        self.file_ext = '.mat'
        self.root_path = '..\\Data\\BSR\\BSDS500\\data\\groundTruth\\'
        self.stored_data_path = self.root_path + 'ProcessedData\\'
        self.stored_file_name = 'processedLabels.pkl'
        self.sampled_file_name = 'downsampledLabels.pkl'
        self.paths = [self.root_path + i for i in ['train', 'test', 'val']]
        self.mat_key = 'groundTruth'
        self.segmentation_index = 0
        self.boundary_index = 1
        self.downsample_ratio = downsampleRatio

    def readFile(self, file):
        mat = scipy.io.loadmat(file)
        mat_data = np.squeeze(mat[self.mat_key][0, 0]).item(0)
        datum = mat_data[self.segmentation_index]  # segementation ground truth, mat_data[1] is the boundary boxes
        datum_downsampled = downsample(datum, ratio=self.downsample_ratio,
                                       interpolation=cv2.INTER_NEAREST)
        # datum1 = mat_data[1]
        # plt.imshow(datum)
        # plt.show()
        return datum, datum_downsampled


class BSRImages(DataSet):
    def __init__(self, downsampleRatio):
        super(BSRImages, self).__init__()
        self.file_ext = '.jpg'
        self.root_path = '..\\Data\\BSR\\BSDS500\\data\\images\\'
        self.stored_data_path = self.root_path + 'ProcessedData\\'
        self.stored_file_name = 'processedImages.pkl'
        self.sampled_file_name = 'downsampledImages.pkl'
        self.paths = [self.root_path + i for i in ['train', 'test', 'val']]
        self.downsample_ratio = downsampleRatio

    def readFile(self, file):
        datum = scipy.misc.imread(file)
        datum_downsampled = downsample(datum, ratio=self.downsample_ratio,
                                       interpolation=cv2.INTER_LINEAR)
        return datum, datum_downsampled


def process_BSR(x_dtype=np.float16, y_dtype=np.float16, downsample_ratio=4):  # c x h x w
    labels = BSRLabels(downsample_ratio)
    images = BSRImages(downsample_ratio)
    x_full, x = images.getData()
    y_full, y = labels.getData()
    if x.dtype != x_dtype:
        x = x.astype(x_dtype)
    if y.dtype != y_dtype:
        y = y.astype(y_dtype)
    x = cleanInput(x)
    assert not np.any(np.isnan(x))
    assert not np.any(np.isnan(y))
    return x, x_full, y, y_full


def downsample(img, ratio, interpolation = cv2.INTER_NEAREST):
    new_h = img.shape[0] // ratio
    new_w = img.shape[1] // ratio
    img = cv2.resize(img, (new_h, new_w), interpolation=interpolation)
    return img


def main():
    x, y = process_BSR()


if __name__ == '__main__':
    main()


def cleanInput(x):
    print('...reshaped from ', x.shape)
    if len(x.shape) > 3:
        x = np.transpose(x, (0, 3, 1, 2))
        x = x / np.max(x)  # scale [0,255] -> [0,1]
    print('to ', x.shape)
    return x


def getClassWeights(y):
    unique, counts = np.unique(y, return_counts=True)
    totalCount = sum(counts)
    return [totalCount / c for c in counts]
