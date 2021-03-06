'''
Define MNIST models
'''

import copy
import random

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions.normal import Normal


class KNNModel(nn.Module):
    '''
    A Pytorch model that apply an identiy function to the input (i.e. output =
    input). It is used to simulate kNN on the input space so that it is
    compatible with attacks implemented for DkNN.
    '''

    def __init__(self):
        super(KNNModel, self).__init__()
        self.identity = nn.Identity()

    def forward(self, x):
        x = self.identity(x)
        return x


# ============================================================================ #


class BasicModel(nn.Module):

    def __init__(self, num_classes=10):
        super(BasicModel, self).__init__()
        self.conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc = nn.Linear(2048, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.conv3(x)
        x = self.relu3(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x


# ============================================================================ #


class BasicModelV2(nn.Module):

    def __init__(self, num_classes=10):
        super(BasicModelV2, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=5, stride=1, padding=2)
        self.relu1 = nn.ReLU(inplace=True)
        self.maxpool1 = nn.MaxPool2d(2, stride=2)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=5, stride=1, padding=2)
        self.relu2 = nn.ReLU(inplace=True)
        self.maxpool2 = nn.MaxPool2d(2, stride=2)
        self.fc1 = nn.Linear(64 * 7 * 7, 1024)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc2 = nn.Linear(1024, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.relu1(self.conv1(x))
        x = self.maxpool1(x)
        x = self.relu2(self.conv2(x))
        x = self.maxpool2(x)
        x = x.view(x.size(0), -1)
        x = self.relu3(self.fc1(x))
        x = self.fc2(x)
        return x


# ============================================================================ #


class ClassAuxVAE(nn.Module):

    def __init__(self, input_dim, num_classes=10, latent_dim=20):
        super(ClassAuxVAE, self).__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.input_dim_flat = 1
        for dim in input_dim:
            self.input_dim_flat *= dim
        self.en_conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.en_conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.en_conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.en_fc1 = nn.Linear(2048, 128)
        self.relu4 = nn.ReLU(inplace=True)
        self.en_mu = nn.Linear(128, latent_dim)
        self.en_logvar = nn.Linear(128, latent_dim)

        self.de_fc1 = nn.Linear(latent_dim, 128)
        self.de_fc2 = nn.Linear(128, self.input_dim_flat * 2)

        # TODO: experiment with different auxilary architecture
        self.ax_fc1 = nn.Linear(latent_dim, 128)
        self.ax_fc2 = nn.Linear(128, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def encode(self, x):
        x = self.relu1(self.en_conv1(x))
        x = self.relu2(self.en_conv2(x))
        x = self.relu3(self.en_conv3(x))
        x = x.view(x.size(0), -1)
        x = self.relu4(self.en_fc1(x))
        en_mu = self.en_mu(x)
        # TODO: use tanh activation on logvar if unstable
        # en_std = torch.exp(0.5 * x[:, self.latent_dim:])
        en_logvar = self.en_logvar(x)
        return en_mu, en_logvar

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        x = F.relu(self.de_fc1(z))
        x = self.de_fc2(x)
        de_mu = x[:, :self.input_dim_flat]
        # de_std = torch.exp(0.5 * x[:, self.input_dim_flat:])
        de_logvar = x[:, self.input_dim_flat:].tanh()
        out_dim = (z.size(0), ) + self.input_dim
        return de_mu.view(out_dim).sigmoid(), de_logvar.view(out_dim)

    def auxilary(self, z):
        x = F.relu(self.ax_fc1(z))
        x = self.ax_fc2(x)
        return x

    def forward(self, x):
        en_mu, en_logvar = self.encode(x)
        z = self.reparameterize(en_mu, en_logvar)
        de_mu, de_logvar = self.decode(z)
        y = self.auxilary(z)
        return en_mu, en_logvar, de_mu, de_logvar, y


# ============================================================================ #


class VAE2(nn.Module):

    def __init__(self, input_dim, num_classes=10, latent_dim=20):
        super(VAE2, self).__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.input_dim_flat = 1
        for dim in input_dim:
            self.input_dim_flat *= dim
        self.en_conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.en_conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.en_conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        # self.relu3 = nn.ReLU(inplace=True)
        self.relu3 = nn.ReLU()
        self.en_fc1 = nn.Linear(2048, 400)
        self.relu4 = nn.ReLU(inplace=True)
        self.en_mu = nn.Linear(400, latent_dim)
        self.en_logvar = nn.Linear(400, latent_dim)

        self.de_fc1 = nn.Linear(latent_dim, 400)
        self.de_relu1 = nn.ReLU(inplace=True)
        self.de_fc2 = nn.Linear(400, self.input_dim_flat)

    def encode(self, x):
        x = self.relu1(self.en_conv1(x))
        x = self.relu2(self.en_conv2(x))
        x = self.relu3(self.en_conv3(x))
        x = x.view(x.size(0), -1)
        x = self.relu4(self.en_fc1(x))
        en_mu = self.en_mu(x)
        # TODO: use tanh activation on logvar if unstable
        # en_std = torch.exp(0.5 * x[:, self.latent_dim:])
        en_logvar = self.en_logvar(x)
        return en_mu, en_logvar

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        x = self.de_relu1(self.de_fc1(z))
        x = self.de_fc2(x)
        out_dim = (z.size(0), ) + self.input_dim
        return x.view(out_dim).sigmoid()

    def forward(self, x):
        en_mu, en_logvar = self.encode(x)
        z = self.reparameterize(en_mu, en_logvar)
        output = self.decode(z)
        return en_mu, en_logvar, output


# ============================================================================ #


class VAE(nn.Module):

    def __init__(self, input_dim, num_classes=10, latent_dim=20):
        super(VAE, self).__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.input_dim_flat = 1
        for dim in input_dim:
            self.input_dim_flat *= dim
        self.en_fc1 = nn.Linear(self.input_dim_flat, 400)
        self.en_relu1 = nn.ReLU(inplace=True)
        self.en_fc2 = nn.Linear(400, 400)
        self.en_relu2 = nn.ReLU(inplace=True)
        self.en_mu = nn.Linear(400, latent_dim)
        self.en_logvar = nn.Linear(400, latent_dim)

        self.de_fc1 = nn.Linear(latent_dim, 400)
        self.de_relu1 = nn.ReLU(inplace=True)
        self.de_fc2 = nn.Linear(400, self.input_dim_flat)

    def encode(self, x):
        x = x.view(-1, self.input_dim_flat)
        x = self.en_relu1(self.en_fc1(x))
        x = self.en_relu2(self.en_fc2(x))
        en_mu = self.en_mu(x)
        # TODO: use tanh activation on logvar if unstable
        # en_std = torch.exp(0.5 * x[:, self.latent_dim:])
        en_logvar = self.en_logvar(x)
        return en_mu, en_logvar

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        x = self.de_relu1(self.de_fc1(z))
        x = self.de_fc2(x)
        out_dim = (z.size(0), ) + self.input_dim
        return x.view(out_dim).sigmoid()

    def forward(self, x):
        en_mu, en_logvar = self.encode(x)
        z = self.reparameterize(en_mu, en_logvar)
        output = self.decode(z)
        return en_mu, en_logvar, output


# ============================================================================ #


class SNNLModel(nn.Module):

    def __init__(self, num_classes=10, train_it=False):
        super(SNNLModel, self).__init__()
        self.conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc = nn.Linear(2048, num_classes)

        # initialize inverse temperature for each layer
        self.it = torch.nn.Parameter(
            data=torch.tensor([-4.6, -4.6, -4.6]), requires_grad=train_it)

        # set up hook to get representations
        self.layers = ['relu1', 'relu2', 'relu3']
        self.activations = {}
        for name, module in self.named_children():
            if name in self.layers:
                module.register_forward_hook(self._get_activation(name))

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _get_activation(self, name):
        def hook(model, input, output):
            self.activations[name] = output
        return hook

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.conv3(x)
        x = self.relu3(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x

    def loss_function(self, x, y_target, alpha=-1):
        """soft nearest neighbor loss"""
        snn_loss = torch.zeros(1).cuda()
        y_pred = self.forward(x)
        for l, layer in enumerate(self.layers):
            rep = self.activations[layer]
            rep = rep.view(x.size(0), -1)
            for i in range(x.size(0)):
                mask_same = (y_target[i] == y_target).type(torch.float32)
                mask_self = torch.ones(x.size(0)).cuda()
                mask_self[i] = 0
                dist = ((rep[i] - rep) ** 2).sum(1) * self.it[l].exp()
                # dist = ((rep[i] - rep) ** 2).sum(1) * 0.01
                # TODO: get nan gradients at
                # Function 'MulBackward0' returned nan values in its 1th output.
                exp = torch.exp(- torch.min(dist, torch.tensor(50.).cuda()))
                # exp = torch.exp(- dist)
                snn_loss += torch.log(torch.sum(mask_self * mask_same * exp) /
                                      torch.sum(mask_self * exp))

        ce_loss = F.cross_entropy(y_pred, y_target)
        return y_pred, ce_loss - alpha / x.size(0) * snn_loss


# ============================================================================ #


class HiddenMixupModel(nn.Module):

    def __init__(self, num_classes=10):
        super(HiddenMixupModel, self).__init__()
        self.conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc = nn.Linear(2048, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x, target=None, mixup_hidden=False, mixup_alpha=0.1,
                layer_mix=None):

        if mixup_hidden:
            if layer_mix is None:
                # TODO: which layers?
                layer_mix = random.randint(0, 4)

            if layer_mix == 0:
                x, y_a, y_b, lam = self.mixup_data(x, target, mixup_alpha)
            x = self.conv1(x)
            x = self.relu1(x)

            if layer_mix == 1:
                x, y_a, y_b, lam = self.mixup_data(x, target, mixup_alpha)
            x = self.conv2(x)
            x = self.relu2(x)

            if layer_mix == 2:
                x, y_a, y_b, lam = self.mixup_data(x, target, mixup_alpha)
            x = self.conv3(x)
            x = self.relu3(x)

            if layer_mix == 3:
                x, y_a, y_b, lam = self.mixup_data(x, target, mixup_alpha)
            x = x.view(x.size(0), -1)
            x = self.fc(x)

            if layer_mix == 4:
                x, y_a, y_b, lam = self.mixup_data(x, target, mixup_alpha)

            # lam = torch.tensor(lam).cuda()
            # lam = lam.repeat(y_a.size())
            return x, y_a, y_b, lam

        else:
            x = self.conv1(x)
            x = self.relu1(x)
            x = self.conv2(x)
            x = self.relu2(x)
            x = self.conv3(x)
            x = self.relu3(x)
            x = x.view(x.size(0), -1)
            x = self.fc(x)
            return x

    @staticmethod
    def loss_function(y_pred, y_a, y_b, lam):
        loss = lam * F.cross_entropy(y_pred, y_a) + \
            (1 - lam) * F.cross_entropy(y_pred, y_b)
        return loss

    @staticmethod
    def mixup_data(x, y, alpha):
        '''
        Compute the mixup data. Return mixed inputs, pairs of targets, and
        lambda. Code from
        https://github.com/vikasverma1077/manifold_mixup/blob/master/supervised/models/utils.py
        '''
        if alpha > 0.:
            lam = np.random.beta(alpha, alpha)
        else:
            lam = 1.
        index = torch.randperm(x.size(0)).cuda()
        mixed_x = lam * x + (1 - lam) * x[index, :]
        y_a, y_b = y, y[index]
        return mixed_x, y_a, y_b, lam


# ============================================================================ #


class Autoencoder(nn.Module):

    def __init__(self, input_dim, latent_dim=20):
        super(Autoencoder, self).__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.input_dim_flat = 1
        for dim in input_dim:
            self.input_dim_flat *= dim
        self.conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc = nn.Linear(2048, 400)
        self.relu4 = nn.ReLU(inplace=True)
        self.latent = nn.Linear(400, latent_dim)

        self.de_fc1 = nn.Linear(latent_dim, 400)
        self.relu5 = nn.ReLU(inplace=True)
        self.de_fc2 = nn.Linear(400, self.input_dim_flat)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def encode(self, x):
        x = self.relu1(self.conv1(x))
        x = self.relu2(self.conv2(x))
        x = self.relu3(self.conv3(x))
        x = x.view(x.size(0), -1)
        x = self.relu4(self.fc(x))
        x = self.latent(x)
        return x

    def decode(self, z):
        x = self.relu5(self.de_fc1(z))
        x = self.de_fc2(x)
        out_dim = (z.size(0), ) + self.input_dim
        return x.view(out_dim)

    def forward(self, x):
        z = self.encode(x)
        out = self.decode(z)
        return z, out

    def loss_function(self, latent, x_recon, inputs, targets):
        # MSE loss
        return torch.sum((inputs - x_recon) ** 2)


# ============================================================================ #


class NCAModel(nn.Module):

    def __init__(self, output_dim=100, init_it=1e-2, train_it=False):
        super(NCAModel, self).__init__()
        self.conv1 = nn.Conv2d(1, 64, kernel_size=8, stride=2, padding=3)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=6, stride=2, padding=3)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3 = nn.Conv2d(128, 128, kernel_size=5, stride=1, padding=0)
        self.relu3 = nn.ReLU(inplace=True)
        self.fc = nn.Linear(2048, output_dim)

        # initialize inverse temperature for each layer
        self.log_it = torch.nn.Parameter(
            data=torch.tensor(np.log(init_it)), requires_grad=train_it)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.conv3(x)
        x = self.relu3(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x

    def forward_adv(self, x, y_target, step_size, num_steps, rand):
        """
        """
        # training samples that we want to query against should not be perturbed
        # so we keep an extra copy and detach it from gradient computation
        outputs_orig = self.forward(x)

        x = x.detach()
        if rand:
            # x = x + torch.zeros_like(x).uniform_(-self.epsilon, self.epsilon)
            x = x + torch.zeros_like(x).normal_(0, step_size)

        for _ in range(num_steps):
            x.requires_grad_()
            with torch.enable_grad():
                outputs = self.forward(x)
                p_target = self.get_prob(
                    outputs, y_target, x_orig=outputs_orig.detach())
                loss = - torch.log(p_target).sum()
            grad = torch.autograd.grad(loss, x)[0].detach()
            grad_norm = grad.view(x.size(0), -1).norm(2, 1)
            delta = step_size * grad / grad_norm.view(x.size(0), 1, 1, 1)
            x = x.detach() + delta
            # x = torch.min(torch.max(x, inputs - self.epsilon),
            #               inputs + self.epsilon)
            x = torch.clamp(x, 0, 1)
            # import pdb
            # pdb.set_trace()

        return outputs_orig, self.forward(x)

    def get_prob(self, x, y_target, x_orig=None):
        """
        If x_orig is given, compute distance w.r.t. x_orig instead of samples
        in the same batch (x). It is intended to be used with adversarial
        training.
        """
        if x_orig is not None:
            assert x.size(0) == x_orig.size(0)

        batch_size = x.size(0)
        p_target = torch.zeros(batch_size, device=x.device)

        for i in range(batch_size):
            mask_same = (y_target[i] == y_target).float()
            mask_not_self = torch.ones(batch_size, device=x.device)
            mask_not_self[i] = 0
            if x_orig is not None:
                dist = ((x[i] - x_orig) ** 2).view(batch_size, -1).sum(1) * \
                    self.log_it.exp()
            else:
                dist = ((x[i] - x) ** 2).view(batch_size, -1).sum(1) * \
                    self.log_it.exp()
            # clip dist to prevent overflow
            exp = torch.exp(- torch.min(dist, torch.tensor(50.).cuda()))
            # exp = torch.exp(- dist)
            p_target[i] = (torch.sum(mask_not_self * mask_same * exp) /
                           torch.sum(mask_not_self * exp))
            # import pdb
            # pdb.set_trace()
        return p_target

    def loss_function(self, output, y_target, orig=None):
        """soft nearest neighbor loss"""
        p_target = self.get_prob(output, y_target, x_orig=orig)
        # y_pred = p_target.max(1)
        loss = - torch.log(p_target)
        return loss.mean()
