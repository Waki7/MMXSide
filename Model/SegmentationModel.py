from Model.Encoders import *
from Model.Decoders import *
import Model.Config as cfg
import Model.Utilities as utils
from os.path import join, isfile
import data_processing.DataProcessor as data
import matplotlib.pyplot as plt
import numpy as np


class SegmentationModel(nn.Module):
    def __init__(self, in_shape, n_class, out_shape, dilation=2, size=128, encoding_size=256):
        super(SegmentationModel, self).__init__()
        self.encoder = SegEncoder(in_shape=in_shape, model_size=size, out_shape=encoding_size, dilation=dilation,
                                  encoding_downsample = cfg.encoding_downsample)
        self.decoder = SegDecoder(n_class=n_class, n_encoded_channels=self.encoder.out_shape,
                                  out_shape=out_shape, size=size)

    def forward(self, input):
        encoded_features = self.encoder(input)
        pred = self.decoder(encoded_features)
        return pred


class Segmenter():
    def __init__(self, model: SegmentationModel = None, downsample_ratio=2,
                 lr=.01, model_size=128, encoding_size=512,
                 data: data.ProcessedDataSet = None):
        self.size_scale = model_size
        self.encoding_size = encoding_size
        self.downsample_ratio = downsample_ratio
        self.lr = lr
        self.model_path = cfg.stored_model_path + '.pkl'
        self.model = model
        self.data = data
        if model is None:
            self.build_model()

    def build_model(self):
        self.load_data()
        self.classes = int(len(self.class_weights))
        self.model = SegmentationModel(in_shape=self.data.x_shape,
                                       n_class=self.classes,
                                       out_shape=self.data.y.shape[-2:],
                                       size=self.size_scale,
                                       encoding_size=self.encoding_size).to(**cfg.args)
        self.opt = torch.optim.SGD(
            self.model.parameters(),
            lr=self.lr,
            momentum=0.9,
            # weight_decay=.001
        )
        self.criterion = nn.NLLLoss(ignore_index=self.data.ignore_index,
                                    reduction='mean', weight=self.class_weights if cfg.weights else None)

    def load_data(self):
        self.data.load_data()
        self.class_weights = torch.tensor(self.data.get_class_weights()).to(**cfg.args)

    def train(self, epochs=10, batch_size=10, checkpoint_space=5):
        x_train, y_train = self.data.get_train_data()
        x_val, y_val = self.data.get_val_data()
        n_train = x_train.shape[0]
        self.model.train()
        mean_loss = 0
        for e in range(epochs):
            shuffled_indexes = torch.randperm(n_train)
            for i in range(0, n_train, batch_size):
                indexes = shuffled_indexes[i:i + batch_size]
                x_batch, y_batch = x_train[indexes], y_train[indexes]
                x_batch, y_batch = torch.tensor(x_batch).to(**cfg.args), torch.tensor(y_batch).to(cfg.device).long()
                y_out = self.model.forward(x_batch)
                loss = self.criterion.forward(input=y_out, target=y_batch)
                mean_loss += loss.data.item()
                loss.backward(retain_graph=False)
                self.opt.step()
                self.opt.zero_grad()
            print(' average loss for epoch ', e, ': ', mean_loss / n_train, **cfg.prnt)
            if e % checkpoint_space == checkpoint_space - 1:
                print('val accuracy ', self.pixel_accuracy(x_val, y_val, batch_size), **cfg.prnt)
                print('train accuracy ', self.pixel_accuracy(x_train, y_train, batch_size), **cfg.prnt)
            mean_loss = 0
        return self.model

    def pixel_accuracy(self, x, y, batch_size):
        predictions = self.predict(x, batch_size)
        return utils.accuracy(predictions, y, self.data.ignore_index)

    def predict(self, x, batch_size=1):
        self.model.eval()
        predictions = []
        for i in range(0, x.shape[0], batch_size):
            x_batch = torch.tensor(x[i:i + batch_size]).to(**cfg.args)
            prediction = self.model.forward(x_batch)
            prediction = prediction.detach().cpu().numpy()
            prediction = np.argmax(prediction, axis=1)
            prediction = prediction
            predictions.append(prediction)
        predictions = np.concatenate(predictions, axis=0)
        self.model.train()
        return predictions

    def test(self, batch_size):
        x_test, y_test = self.data.get_test_data()
        y_pred_test = self.predict(x_test, batch_size)
        print('test accuracy ', utils.accuracy(y_pred_test, y_test, self.data.ignore_index), **cfg.prnt)

        x_full, y_full = self.data.get_full_data()
        y_pred_full = self.predict(x_full, batch_size)
        print('accuracy for whole dataset', utils.accuracy(y_pred_full, y_full, self.data.ignore_index), **cfg.prnt)

        utils.plot_confusion_matrix(y_pred_test, y_test, 'test')
        utils.plot_confusion_matrix(y_pred_full, y_full, 'full')

    def show_predictions(self, x, y, idx):
        self.model.eval()
        _, ax = plt.subplots(1, 2)
        x_batch = torch.tensor(x[idx:idx + 1]).to(**cfg.args)
        prediction = self.model.forward(x_batch)
        prediction = prediction.detach().cpu().numpy()
        prediction = np.argmax(prediction, axis=1)
        prediction = prediction[0]
        ground_truth = y[idx:idx + 1][0]
        ax[0].imshow(prediction)
        ax[1].imshow(ground_truth)
        plt.show()
        self.model.train()

    def save_model(self):
        torch.save(self.model, self.model_path)

    def load_model(self):
        if isfile(self.model_path):
            self.model = torch.load(self.model_path)
            return True
        return False


def main(): #todo https://github.com/meetshah1995/pytorch-semseg
    print(cfg.lr, **cfg.prnt)
    dataset = data.get_experiment_data()(downsample_ratio=cfg.downsample_ratio)
    segmenter = Segmenter(lr=cfg.lr, downsample_ratio=cfg.downsample_ratio, model_size=cfg.model_size,
                          encoding_size=cfg.encoding_size, data=dataset)
    if cfg.load_model:
        segmenter.load_model()
    else:
        segmenter.train(epochs=cfg.epochs, batch_size=cfg.batch_size)
        segmenter.save_model()

        segmenter.test(cfg.batch_size)
    x, y = segmenter.data.get_train_data()
    segmenter.show_predictions(x, y, 1)
    x, y = segmenter.data.get_test_data()
    segmenter.show_predictions(x, y, 1)
    print('_______________', **cfg.prnt)


if __name__ == '__main__':
    main()
