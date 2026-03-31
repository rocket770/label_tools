import numpy as np
import cv2


def generate_hsv_color_table(n=255):
    """
    生成 n 种均匀分布的颜色，使用 HSV 色环转换为 RGB。
    """
    rng = np.random.RandomState(0)
    hsv_colors = np.linspace(0, 179, n, dtype=np.uint8)
    rng.shuffle(hsv_colors)
    color_table = np.zeros((n, 3), dtype=np.uint8)

    for i, hue in enumerate(hsv_colors):
        # 将 HSV 转换为 BGR（OpenCV 默认使用 BGR 格式）
        bgr = cv2.cvtColor(np.array([[[hue, 255, 255]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)
        color_table[i] = bgr[0][0]

    return color_table


class ColorMapper:

    def __init__(self):
        self.color_table = generate_hsv_color_table()
        print(self.color_table.max())

    def apply_custom_color_map_with_alpha(self, data, alpha=255):
        """
        将灰度图像的每个像素值映射到完全不同的颜色，并处理透明度。
        0 映射为完全透明，其他值映射为不同的颜色。
        """
        
        # 创建一个与 data 相同形状的空数组，准备存储 RGBA 图像
        height, width = data.shape
        color_data = np.zeros((height, width, 4), dtype=np.uint8)  # 4 通道（RGBA）

        # 找到灰度值为 0 的像素
        zero_mask = (data == 0)

        # 设置完全透明的像素（灰度值为 0）
        color_data[zero_mask] = [0, 0, 0, 0]  # RGBA (0, 0, 0, 0) 表示完全透明

        # 为非零灰度值的像素设置颜色
        non_zero_mask = ~zero_mask  # 反转 mask，选择非零的灰度值
        color_data[non_zero_mask, 0:3] = self.color_table[data[non_zero_mask] % len(self.color_table)]

        # 设置 alpha 为 255（完全不透明）
        color_data[non_zero_mask, 3] = alpha  # Alpha 通道设置为 255

        return color_data