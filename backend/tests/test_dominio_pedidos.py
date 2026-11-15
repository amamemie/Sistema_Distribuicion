from decimal import Decimal as D

from app.modules.pedidos import dominio


def test_aritmetica_correcta_no_avisa() -> None:
    lineas = [
        dominio.LineaOC(1, D(10), D("2.50"), D("25.00")),
        dominio.LineaOC(2, D(3), D("1.3333"), D("4.00")),
    ]
    assert dominio.validar_aritmetica(lineas, D("29.00")) == []


def test_aritmetica_detecta_linea_y_total() -> None:
    lineas = [
        dominio.LineaOC(1, D(10), D("2.50"), D("250.00")),  # error de lectura típico
        dominio.LineaOC(2, D(2), D("5"), None),  # sin total impreso: se usa el calculado
    ]
    avisos = dominio.validar_aritmetica(lineas, D("35.00"))
    assert avisos[0][0] == 1
    assert "Bs 25.00" in avisos[0][1] and "Bs 250.00" in avisos[0][1]
    assert avisos[1][0] is None and "Bs 260.00" in avisos[1][1]


def test_rentabilidad() -> None:
    r = dominio.rentabilidad(D("135"), D("90.456"))
    assert (r.ingreso, r.costo, r.ganancia, r.margen) == (
        D("135.00"),
        D("90.46"),
        D("44.54"),
        D("32.99"),
    )
    assert dominio.rentabilidad(D(0), D(5)).margen is None


def test_normalizacion_para_equivalencias() -> None:
    assert dominio.normalizar_descripcion("  Detergente   ÁLA  1Kg ") == "detergente ala 1kg"
    assert dominio.normalizar_codigo(" 77 01 ab ") == "7701AB"
    assert dominio.claves_equivalencia("  ", "Leche") == ["D:leche"]
    assert dominio.claves_equivalencia("X1", "Leche") == ["C:X1", "D:leche"]
