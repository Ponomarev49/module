import pandas as pd
import numpy as np
from scipy.signal import find_peaks

def read_and_process_file2(file_path: str, table_name: str):
    # Читаем все данные, включая строку с названиями параметров
    df = pd.read_excel(file_path, sheet_name=table_name, skiprows=5, header=None, dtype=str)

    # Первая строка (индекс 0) - это названия параметров
    param_names = df.iloc[0].values

    # Данные начиная с индекса 1 (включая первую строку данных)
    data = df.iloc[1:].reset_index(drop=True)

    # Присваиваем названия столбцов
    data.columns = param_names

    # Удаляем полностью пустые строки
    data = data.dropna(how='all').reset_index(drop=True)

    param_dfs = {}

    # Проходим по колонкам парами
    i = 0
    while i < len(data.columns):
        param_name = data.columns[i]

        # Проверяем, что это название параметра
        if pd.notna(param_name) and str(param_name).strip() and 'Unnamed' not in str(param_name):
            # Проверяем, что есть следующий столбец
            if i + 1 < len(data.columns):
                # Создаем DataFrame с данными
                param_data = pd.DataFrame({
                    'Время': data.iloc[:, i],
                    'Значение': data.iloc[:, i + 1]
                })

                # Удаляем строки где оба значения NaN
                param_data = param_data.dropna(subset=['Время', 'Значение'], how='all').reset_index(drop=True)

                if not param_data.empty:
                    # ОБРЕЗАЕМ МИЛЛИСЕКУНДЫ В СТРОКЕ (до конвертации)
                    param_data['Время'] = param_data['Время'].str.replace(r'\..*$', '', regex=True)

                    # КОНВЕРТАЦИЯ ДАННЫХ
                    param_data['Время'] = pd.to_datetime(param_data['Время'], errors='coerce')
                    param_data['Значение'] = pd.to_numeric(param_data['Значение'], errors='coerce')

                    # Удаляем строки с некорректным временем или значением
                    param_data = param_data.dropna(subset=['Время', 'Значение']).reset_index(drop=True)

                    if not param_data.empty:
                        # УСТАНАВЛИВАЕМ ВРЕМЯ КАК ИНДЕКС
                        param_data = param_data.set_index('Время')

                        param_dfs[str(param_name)] = param_data

            i += 2  # Переходим к следующей паре
        else:
            i += 1  # Пропускаем некорректный столбец

    return param_dfs


def analyze_delay_and_maxima(setpoint_data, output_data, max_shift=500,
                              lower_quantile=0.15, upper_quantile=0.95, peak_distance=1):
    # === ЧАСТЬ 1: Поиск оптимального сдвига (задержки) ===

    def find_optimal_shift_bruteforce(values1, values2, max_shift, metric='mae'):
        errors = []
        shifts = list(range(-max_shift, max_shift + 1))

        for shift in shifts:
            if shift < 0:
                v1 = values1[:shift] if shift != 0 else values1
                v2 = values2[-shift:] if shift != 0 else values2
            elif shift > 0:
                v1 = values1[shift:]
                v2 = values2[:-shift] if shift != 0 else values2
            else:
                min_len = min(len(values1), len(values2))
                v1 = values1[:min_len]
                v2 = values2[:min_len]

            if len(v1) == 0 or len(v2) == 0:
                errors.append(np.inf)
                continue

            if metric == 'mae':
                error = np.mean(np.abs(v2 - v1))
            else:
                error = np.mean((v2 - v1) ** 2)

            errors.append(error)

        errors = np.array(errors)
        best_idx = np.argmin(errors)
        best_shift = shifts[best_idx]
        best_error = errors[best_idx]

        return best_shift, best_error, errors, shifts

    def align_series(values1, values2, shift):
        if shift == 0:
            min_len = min(len(values1), len(values2))
            return values1[:min_len], values2[:min_len]
        elif shift > 0:
            v1 = values1[shift:]
            v2 = values2[:-shift]
        else:
            v1 = values1[:shift]
            v2 = values2[-shift:]

        min_len = min(len(v1), len(v2))
        return v1[:min_len], v2[:min_len]

    # Преобразуем в numpy массивы
    values1 = np.array(setpoint_data)
    values2 = np.array(output_data)

    # Исходная ошибка (без сдвига)
    min_len_orig = min(len(values1), len(values2))
    mae_original = np.mean(np.abs(values2[:min_len_orig] - values1[:min_len_orig]))

    # Поиск оптимального сдвига
    delay, bf_error_mae, _, _ = find_optimal_shift_bruteforce(
        values1, values2, max_shift=max_shift, metric='mae'
    )

    # Выравниваем ряды с оптимальным сдвигом
    aligned_v1, aligned_v2 = align_series(values1, values2, delay)

    # Вычисляем ошибку со сдвигом
    min_len_aligned = min(len(aligned_v1), len(aligned_v2))
    mae_shifted = np.mean(np.abs(aligned_v2[:min_len_aligned] - aligned_v1[:min_len_aligned]))

    # Вычисляем модуль ошибки со сдвигом для анализа максимумов
    error_shifted = aligned_v2[:min_len_aligned] - aligned_v1[:min_len_aligned]
    abs_error_shifted = np.abs(error_shifted)

    # === ЧАСТЬ 2: Анализ максимумов модуля ошибки ===

    # Находим все локальные максимумы модуля ошибки
    peaks_idx, _ = find_peaks(abs_error_shifted, distance=peak_distance)
    all_peaks = abs_error_shifted[peaks_idx]

    n_peaks = len(all_peaks)
    n_remove_lower = int(n_peaks * lower_quantile)
    n_remove_upper = int(n_peaks * (1 - upper_quantile))

    # Вычисляем границы отсечения
    lower_bound = np.quantile(all_peaks, lower_quantile) if n_peaks > 0 else 0
    upper_bound = np.quantile(all_peaks, upper_quantile) if n_peaks > 0 else 0

    # Фильтруем максимумы
    mask = (all_peaks >= lower_bound) & (all_peaks <= upper_bound)
    filtered_peaks = all_peaks[mask]

    # Считаем среднее и медиану оставшихся
    mean_maxima = np.mean(filtered_peaks) if len(filtered_peaks) > 0 else 0
    median_maxima = np.median(filtered_peaks) if len(filtered_peaks) > 0 else 0

    # Вычисляем задержку в часах: delay * 5 / 3600
    delay_hours = delay * 5 / 3600

    # Вычисляем отношение mean_maxima / delay_hours
    maxima_ratio = mean_maxima / delay_hours if delay_hours != 0 else 0

    # Возвращаем результаты
    return {
        'delay': delay,
        'delay_hours': delay_hours,
        'original_mae': mae_original,
        'shifted_mae': mae_shifted,
        'improvement': (1 - mae_shifted / mae_original) * 100 if mae_original > 0 else 0,
        'mean_maxima': mean_maxima,
        'median_maxima': median_maxima,
        'maxima_ratio': maxima_ratio,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'n_peaks_total': n_peaks,
        'n_peaks_filtered': len(filtered_peaks),
        'n_removed_lower': n_remove_lower,
        'n_removed_upper': n_remove_upper,
        'abs_error_original': np.abs(values2[:min_len_orig] - values1[:min_len_orig]),
        'abs_error_shifted': abs_error_shifted
    }

def algorithm(file_path:str, sheet:str):
    series_dict = read_and_process_file2(file_path, sheet)

    results={}

    for i in range(0, len(series_dict.keys()), 2):
        result = analyze_delay_and_maxima(series_dict[list(series_dict.keys())[i]]["Значение"].values, series_dict[f"{list(series_dict.keys())[i]}_SV"]["Значение"].values, max_shift=500,
                                    lower_quantile=0.15, upper_quantile=0.9, peak_distance=3)
        results[list(series_dict.keys())[i]]=result

    return results