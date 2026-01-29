/****************************************************************************
** Meta object code from reading C++ file 'histograminspector.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "histograminspector.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'histograminspector.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__HistogramInspector_t {
    uint offsetsAndSizes[22];
    char stringdata0[35];
    char stringdata1[15];
    char stringdata2[1];
    char stringdata3[4];
    char stringdata4[29];
    char stringdata5[4];
    char stringdata6[13];
    char stringdata7[10];
    char stringdata8[19];
    char stringdata9[21];
    char stringdata10[19];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__HistogramInspector_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__HistogramInspector_t qt_meta_stringdata_omnetpp__qtenv__HistogramInspector = {
    {
        QT_MOC_LITERAL(0, 34),  // "omnetpp::qtenv::HistogramInsp..."
        QT_MOC_LITERAL(35, 14),  // "onShowCellInfo"
        QT_MOC_LITERAL(50, 0),  // ""
        QT_MOC_LITERAL(51, 3),  // "bin"
        QT_MOC_LITERAL(55, 28),  // "onCustomContextMenuRequested"
        QT_MOC_LITERAL(84, 3),  // "pos"
        QT_MOC_LITERAL(88, 12),  // "onShowCounts"
        QT_MOC_LITERAL(101, 9),  // "onShowPDF"
        QT_MOC_LITERAL(111, 18),  // "onOptionsTriggered"
        QT_MOC_LITERAL(130, 20),  // "onApplyButtonClicked"
        QT_MOC_LITERAL(151, 18)   // "onSetUpBinsClicked"
    },
    "omnetpp::qtenv::HistogramInspector",
    "onShowCellInfo",
    "",
    "bin",
    "onCustomContextMenuRequested",
    "pos",
    "onShowCounts",
    "onShowPDF",
    "onOptionsTriggered",
    "onApplyButtonClicked",
    "onSetUpBinsClicked"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__HistogramInspector[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       7,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   56,    2, 0x08,    1 /* Private */,
       4,    1,   59,    2, 0x08,    3 /* Private */,
       6,    0,   62,    2, 0x08,    5 /* Private */,
       7,    0,   63,    2, 0x08,    6 /* Private */,
       8,    0,   64,    2, 0x08,    7 /* Private */,
       9,    0,   65,    2, 0x08,    8 /* Private */,
      10,    0,   66,    2, 0x08,    9 /* Private */,

 // slots: parameters
    QMetaType::Void, QMetaType::Int,    3,
    QMetaType::Void, QMetaType::QPoint,    5,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::HistogramInspector::staticMetaObject = { {
    QMetaObject::SuperData::link<Inspector::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__HistogramInspector.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__HistogramInspector,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__HistogramInspector_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<HistogramInspector, std::true_type>,
        // method 'onShowCellInfo'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'onCustomContextMenuRequested'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPoint, std::false_type>,
        // method 'onShowCounts'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onShowPDF'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onOptionsTriggered'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onApplyButtonClicked'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onSetUpBinsClicked'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::HistogramInspector::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<HistogramInspector *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->onShowCellInfo((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 1: _t->onCustomContextMenuRequested((*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[1]))); break;
        case 2: _t->onShowCounts(); break;
        case 3: _t->onShowPDF(); break;
        case 4: _t->onOptionsTriggered(); break;
        case 5: _t->onApplyButtonClicked(); break;
        case 6: _t->onSetUpBinsClicked(); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::HistogramInspector::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::HistogramInspector::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__HistogramInspector.stringdata0))
        return static_cast<void*>(this);
    return Inspector::qt_metacast(_clname);
}

int omnetpp::qtenv::HistogramInspector::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = Inspector::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 7)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 7;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 7)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 7;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
