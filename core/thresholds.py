THRESHOLDS_SP = [
    {'threshold': 0, 'label': 'Sertifikat Disiplin', 'color': 'green'},
    {'threshold': -300, 'label': 'SP I (Skorsing 1 hari)', 'color': 'yellow'},
    {'threshold': -400, 'label': 'SP II (Skorsing 1 hari, max ujian 65%)', 'color': 'orange'},
    {'threshold': -500, 'label': 'SP III (Skorsing 2 hari, max ujian 65%)', 'color': 'red'},
    {'threshold': -600, 'label': 'Status diputuskan Rapat Dewan Guru', 'color': 'darkred'}
]

def status_peringatan(total_poin_minus):
    for i in range(len(THRESHOLDS_SP) - 1, -1, -1):
        if total_poin_minus <= THRESHOLDS_SP[i]['threshold']:
            return THRESHOLDS_SP[i]
    return THRESHOLDS_SP[0]


def tingkat_sp(total_mutlak):
    if total_mutlak is None or total_mutlak < 300:
        return None
    return status_peringatan(-total_mutlak)['label']
