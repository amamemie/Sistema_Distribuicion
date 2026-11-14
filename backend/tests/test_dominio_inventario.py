from decimal import Decimal as D

from app.modules.inventario import dominio


def test_conversion_a_unidad_base() -> None:
    assert dominio.a_base(D("4"), D("300")) == D("1200.000")
    assert dominio.a_base(D("2.5"), D("12")) == D("30.000")


def test_cpp_ponderado() -> None:
    # 1200 u a 0.50 + 600 u a 0.80 → (600 + 480) / 1800 = 0.60
    assert dominio.cpp_al_ingresar(D("1200"), D("0.5"), D("600"), D("0.8")) == D("0.600000")
    # Sin saldo previo, el CPP es el costo del ingreso.
    assert dominio.cpp_al_ingresar(D("0"), D("0"), D("10"), D("2.5")) == D("2.500000")


def test_cpp_al_anular_un_ingreso_vuelve_al_anterior() -> None:
    cpp = dominio.cpp_al_ingresar(D("1200"), D("0.5"), D("600"), D("0.8"))
    assert dominio.cpp_al_retirar_a_costo(D("1800"), cpp, D("600"), D("0.8")) == D("0.500000")
    # Si el saldo queda en cero se conserva el último CPP.
    assert dominio.cpp_al_retirar_a_costo(D("10"), D("2"), D("10"), D("2")) == D("2")


def test_prorrateo_proporcional_y_exacto() -> None:
    partes = dominio.prorratear([D("600"), D("300"), D("100")], D("100"))
    assert partes == [D("60.00"), D("30.00"), D("10.00")]
    partes = dominio.prorratear([D("1"), D("1"), D("1")], D("10"))
    assert sum(partes) == D("10.00")
    assert dominio.prorratear([D("5")], D("0")) == [D("0")]


def test_desglose_en_presentaciones() -> None:
    pres = [("Fardo", D("100")), ("Paquete", D("10"))]
    assert dominio.desglose(D("325"), pres, "unidad") == "3 Fardo + 2 Paquete + 5 unidad"
    assert dominio.desglose(D("300"), pres, "unidad") == "3 Fardo"
    assert dominio.desglose(D("7"), pres, "unidad") == "7 unidad"
    assert dominio.desglose(D("0"), pres, "unidad") == "0 unidad"
    assert dominio.desglose(D("2.5"), [], "kg") == "2.5 kg"
