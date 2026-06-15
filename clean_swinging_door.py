import pandas as pd
from collections import defaultdict
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import os


def read_and_process_file(file_path: str):
    # Читаем оба листа ЗА ОДИН РАЗ
    with pd.ExcelFile(file_path) as xls:
        # Читаем лист 'Параметры'
        df_params = pd.read_excel(xls, sheet_name='Параметры', skiprows=2)

        # Читаем лист 'Выборка'
        df_raw = pd.read_excel(xls, sheet_name='Выборка АТ-9', skiprows=6, header=[0, 1])

    # Обработка параметров
    df_params.columns = [col.strip() for col in df_params.columns]
    data_dict = defaultdict(dict)

    for _, row in df_params.iterrows():
        obj = row['Объект']
        param = row['Параметр']

        data_dict[obj][param] = {
            # 'Позиция': row['Позиция'],
            'Массовый расход': row[f'Массовый расход\n(для контроля)'],
            'Направление': row['Направление'],
            'Описание': row['Описание'],
            'Шкала': row['Шкала'],
            'Сжатие, %': round(row['Сжатие, %'], 2)
        }

    # Обработка выборки
    df_clean = df_raw.reset_index(drop=True)
    param_dfs = {}

    for param in df_clean.columns.levels[0]:
        if param not in df_clean.columns:
            continue

        sub_df = df_clean[param][1:].dropna(how='all')
        if not sub_df.empty:
            param_dfs[param] = sub_df.reset_index(drop=True)

    for param, sub_df in param_dfs.items():
        if 'Время' in sub_df.columns:
            sub_df['Время'] = pd.to_datetime(sub_df['Время'], errors='coerce')
            sub_df['Время'] = sub_df['Время'].dt.strftime('%Y-%m-%d %H:%M:%S')
            param_dfs[param] = sub_df

    return data_dict, param_dfs

def swinging_door(df: pd.DataFrame, E: float, verbose: bool = False) -> pd.DataFrame:
    df = df.copy()
    df['Время'] = pd.to_datetime(df['Время'])
    df['Значение'] = pd.to_numeric(df['Значение'], errors='coerce')
    df = df.dropna(subset=['Значение']).reset_index(drop=True)

    if df.empty:
        return df

    result = []

    # Первая опорная точка
    t0 = df.loc[0, 'Время']
    v0 = df.loc[0, 'Значение']
    result.append((t0, v0))

    if verbose:
        print(f"\n{'='*60}")
        print(f"НАЧАЛЬНАЯ ОПОРНАЯ ТОЧКА: Время={t0}, Значение={v0}")
        print(f"{'='*60}")

    # Начальные границы углов наклона
    lower_slope = float('+inf')
    upper_slope = float('-inf')

    last_t = t0
    last_v = v0

    for i in range(1, len(df)):
        ti = df.loc[i, 'Время']
        vi = df.loc[i, 'Значение']

        dt = (ti - t0).total_seconds()

        new_lower = (vi - v0 + E) / dt
        new_upper = (vi - v0 - E) / dt

        old_lower = lower_slope
        old_upper = upper_slope

        if verbose:
            print(f"\n--- Точка {i} ---")
            print(f"ТЕКУЩАЯ точка: Время={ti}, Значение={vi}")
            print(f"ОПОРНАЯ точка: Время={t0}, Значение={v0}")
            print(f"  dt = {dt:.4f} сек")
            print(f"  E = {E}")
            print(f"  new_lower = {new_lower:.6f}")
            print(f"  new_upper = {new_upper:.6f}")
            print(f"  Текущие границы: lower_slope = {lower_slope if lower_slope != float('inf') else 'inf'}, upper_slope = {upper_slope if upper_slope != float('-inf') else '-inf'}")

        lower_slope = min(lower_slope, new_lower)
        upper_slope = max(upper_slope, new_upper)

        if verbose:
            print(f"  Обновленные границы: lower_slope = {lower_slope if lower_slope != float('inf') else 'inf'}, upper_slope = {upper_slope if upper_slope != float('-inf') else '-inf'}")
            print(f"  Условие lower_slope <= upper_slope: {lower_slope <= upper_slope}")

        if lower_slope <= upper_slope:
            if verbose:
                print(f"  *** АЛГОРИТМ ОСТАНАВЛИВАЕТСЯ на текущей точке ***")
                print(f"  Сохраняем последнюю опорную точку: Время={last_t}, Значение={last_v}")
            result.append((last_t, last_v))

            # Новая опорная точка
            t0 = last_t
            v0 = last_v
            dt_new = (ti - t0).total_seconds()

            lower_slope = (vi - v0 + E) / dt_new
            upper_slope = (vi - v0 - E) / dt_new

            if verbose:
                print(f"  НОВАЯ опорная точка: Время={t0}, Значение={v0}")
                print(f"  Сброс границ: lower_slope = {lower_slope:.6f}, upper_slope = {upper_slope:.6f}")
        else:
            if verbose:
                print(f"  *** АЛГОРИТМ ПРОДОЛЖАЕТ (точка в коридоре) ***")

        # Эта точка пока помещается в коридор
        last_t = ti
        last_v = vi

    if (last_t, last_v) != result[-1]:
        if verbose:
            print(f"\n--- ФИНАЛЬНАЯ точка (добавляем последнюю) ---")
            print(f"  Добавляем: Время={last_t}, Значение={last_v}")
        result.append((last_t, last_v))

    if verbose:
        print(f"\n{'='*60}")
        print(f"ИТОГО сохранено точек: {len(result)}")
        print(f"{'='*60}\n")

    return pd.DataFrame(result, columns=['Время', 'Значение'])

def calculate_metrics(original_df, compressed_df):
    """
    Расчет метрик между исходным и сжатым датафреймами

    Parameters:
    original_df: DataFrame - исходный датафрейм с колонками 'Время' и 'Значение'
    compressed_df: DataFrame - сжатый датафрейм с колонками 'Время' и 'Значение'

    Returns:
    dict: словарь с метриками
    """
    # === Размерности исходных данных (ВАЖНО: берем размерность входных данных) ===
    n_original = len(original_df)      # размер исходного датафрейма
    n_compressed = len(compressed_df)  # размер сжатого датафрейма (пришедшего на вход)

    # === Интерполяция сжатых данных на временную сетку исходных ===
    # Преобразуем время в числовой формат
    original_df['Время'] = pd.to_datetime(original_df['Время'])
    time_original = original_df['Время'].astype('int64')
    time_compressed = compressed_df['Время'].astype('int64')

    # Интерполируем значения
    original_values = original_df['Значение'].values
    compressed_values_interp = np.interp(time_original, time_compressed, compressed_df['Значение'].values)

    # === Метрики точности ===
    errors = original_values - compressed_values_interp
    abs_errors = np.abs(errors)

    mae = np.mean(abs_errors)
    mse = np.mean(errors ** 2)
    rmse = np.sqrt(mse)
    max_error = np.max(abs_errors)

    # MAPE (средняя абсолютная процентная ошибка)
    mask = original_values != 0
    if np.any(mask):
        mape = np.mean(np.abs((original_values[mask] - compressed_values_interp[mask]) / original_values[mask])) * 100
    else:
        mape = np.inf

    # MASE (Mean Absolute Scaled Error)
    # Наивный прогноз (используем разницу между последовательными точками)
    n = len(original_values)
    if n > 1:
        # Средняя абсолютная ошибка наивного прогноза (вперед на 1 шаг)
        naive_errors = np.abs(np.diff(original_values))
        naive_mae = np.mean(naive_errors)

        # MASE = MAE / MAE_naive
        if naive_mae != 0:
            mase = mae / naive_mae
        else:
            mase = np.inf
    else:
        mase = np.inf

    # R² (коэффициент детерминации)
    ss_res = np.sum(errors ** 2)
    ss_tot = np.sum((original_values - np.mean(original_values)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    # === Метрики сжатия (основаны на РЕАЛЬНОЙ размерности входных данных) ===
    # Коэффициент сжатия (во сколько раз меньше оригинал)
    compression_ratio = n_original / n_compressed if n_compressed > 0 else np.inf

    # Степень сжатия (сколько процентов данных осталось от оригинала)
    compression_percentage = (n_compressed / n_original) * 100 if n_original > 0 else 0

    # Сколько точек удалили/сохранили
    points_saved = n_original - n_compressed
    points_kept = n_compressed

    # === Комплексные метрики (учитывают реальное сжатие) ===
    # Эффективность сжатия (качество на единицу сжатия)
    compression_efficiency = compression_ratio / (rmse + 1e-10)

    # Качество на точку данных (сколько качества получаем за каждую сохраненную точку)
    quality_per_point = (1 - rmse / (np.std(original_values) + 1e-10)) * compression_ratio

    # Индекс "точность-размер" (PAI - Precision-Accuracy Index)
    pai = ((r2 + 1) / 2) * compression_ratio

    # Отношение сигнал/шум с учетом сжатия
    snr = 10 * np.log10(np.var(original_values) / (rmse ** 2 + 1e-10))
    snr_with_compression = snr * (compression_ratio / 10)

    return {
        # === Базовые метрики точности ===
        'MAE': mae,
        'MAPE (%)': mape,
        'MASE': mase,
        'R²': r2,

        # === Дополнительные метрики точности ===
        'RMSE': rmse,
        'Max Error': max_error,

        # === Метрики сжатия (размерность ВХОДНЫХ данных) ===
        'Compression Ratio': compression_ratio,        # во сколько раз сжали
        'Compression %': compression_percentage,       # % оставшихся данных
        'Points Original': n_original,                 # размер исходного
        'Points Compressed': n_compressed,             # размер сжатого (пришедшего на вход)
        'Points Saved': points_saved,                  # сколько точек удалили
        'Points Kept %': (n_compressed / n_original) * 100,  # процент сохраненных точек

        # === Комплексные метрики ===
        'Compression Efficiency': compression_efficiency,    # эффективность сжатия
        'Quality per Point': quality_per_point,              # качество на точку
        'PAI Index': pai,                                    # точность-размер
        'SNR with Compression': snr_with_compression         # SNR с учетом сжатия
    }

# Красивый вывод всех метрик:
def print_metrics(metrics):
    print("=" * 50)
    print("ОСНОВНЫЕ МЕТРИКИ ТОЧНОСТИ:")
    print("=" * 50)
    print(f"MAE:  {metrics['MAE']:.4f}")
    print(f"MAPE: {metrics['MAPE (%)']:.2f}%")
    print(f"MASE: {metrics['MASE']:.4f}")
    print(f"R²:   {metrics['R²']:.10f}")
    print(f"RMSE: {metrics['RMSE']:.4f}")

    print("\n" + "=" * 50)
    print("МЕТРИКИ СЖАТИЯ:")
    print("=" * 50)
    print(f"Коэффициент сжатия: {metrics['Compression Ratio']:.2f}x")
    print(f"Сжатие: {metrics['Compression %']:.1f}% от оригинала")
    print(f"Сохранено точек: {metrics['Points Saved']} из {metrics['Points Original']}")

def write(file_path: str,compressed_data: dict, sheet_name="Сжатые данные"):
    print("write")
    dfs = []
    params = list(compressed_data.keys())
    num_params = len(params)
    tuples = []

    for param in params:
        df = compressed_data[param][['Время', 'Значение']].reset_index(drop=True)
        dfs.append(df)
        tuples.extend([(param, 'Время'), (param, 'Значение')])

    result_df = pd.concat(dfs, axis=1)

    total_cols = 2 * num_params

    first_header = ["" for _ in range(total_cols)]

    for i, param in enumerate(params):
        pos = i * 2
        first_header[pos] = param

    second_header = []
    third_header = []
    for key in compressed_data.keys():
        second_header.extend(['Время', 'Значение'])
        third_header.extend(['Кол-во значений', len(compressed_data[key])])

    headers_df = pd.DataFrame([first_header, second_header, third_header])

    # === Запись в Excel ===
    if os.path.exists(file_path):
        # Файл уже есть → дописываем новый лист
        with pd.ExcelWriter(file_path, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            headers_df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            result_df.to_excel(writer, sheet_name=sheet_name, startrow=3, index=False, header=False)
    else:
        # Файла нет → создаём новый
        with pd.ExcelWriter(file_path, mode='w', engine='openpyxl', if_sheet_exists='overlay') as writer:
            headers_df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            result_df.to_excel(writer, sheet_name=sheet_name, startrow=3, index=False, header=False)

    print(f"Данные записаны в файл '{file_path}' на лист '{sheet_name}'")

# В конце файла clean_swinginging_door.py добавь:
def algorithm(file_path: str):
    parametrs, samples = read_and_process_file(file_path)
    compressed_data = {}
    all_metrics = {}
    
    for key in samples.keys():
        E = parametrs['АТ-9'][key]['Шкала'] * parametrs['АТ-9'][key]['Сжатие, %']/100
        compressed_df = swinging_door(samples[key], E)
        compressed_data[key] = compressed_df
        
        # Рассчитываем метрики
        metrics_my = calculate_metrics(samples[key], compressed_data[key])
        all_metrics[key] = metrics_my
    
    write(file_path, compressed_data, sheet_name="Сжатые данные")
    
    return compressed_data, all_metrics