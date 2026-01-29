/****************************************************************************
** Meta object code from reading C++ file 'findobjectsdialog.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "findobjectsdialog.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'findobjectsdialog.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog_t {
    uint offsetsAndSizes[24];
    char stringdata0[34];
    char stringdata1[11];
    char stringdata2[1];
    char stringdata3[8];
    char stringdata4[8];
    char stringdata5[12];
    char stringdata6[6];
    char stringdata7[26];
    char stringdata8[15];
    char stringdata9[9];
    char stringdata10[11];
    char stringdata11[14];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog_t qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog = {
    {
        QT_MOC_LITERAL(0, 33),  // "omnetpp::qtenv::FindObjectsDi..."
        QT_MOC_LITERAL(34, 10),  // "invalidate"
        QT_MOC_LITERAL(45, 0),  // ""
        QT_MOC_LITERAL(46, 7),  // "refresh"
        QT_MOC_LITERAL(54, 7),  // "inspect"
        QT_MOC_LITERAL(62, 11),  // "QModelIndex"
        QT_MOC_LITERAL(74, 5),  // "index"
        QT_MOC_LITERAL(80, 25),  // "onListBoxSelectionChanged"
        QT_MOC_LITERAL(106, 14),  // "QItemSelection"
        QT_MOC_LITERAL(121, 8),  // "selected"
        QT_MOC_LITERAL(130, 10),  // "deselected"
        QT_MOC_LITERAL(141, 13)   // "onFontChanged"
    },
    "omnetpp::qtenv::FindObjectsDialog",
    "invalidate",
    "",
    "refresh",
    "inspect",
    "QModelIndex",
    "index",
    "onListBoxSelectionChanged",
    "QItemSelection",
    "selected",
    "deselected",
    "onFontChanged"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__FindObjectsDialog[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       5,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   44,    2, 0x0a,    1 /* Public */,
       3,    0,   45,    2, 0x08,    2 /* Private */,
       4,    1,   46,    2, 0x08,    3 /* Private */,
       7,    2,   49,    2, 0x08,    5 /* Private */,
      11,    0,   54,    2, 0x08,    8 /* Private */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 5,    6,
    QMetaType::Void, 0x80000000 | 8, 0x80000000 | 8,    9,   10,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::FindObjectsDialog::staticMetaObject = { {
    QMetaObject::SuperData::link<QDialog::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__FindObjectsDialog,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<FindObjectsDialog, std::true_type>,
        // method 'invalidate'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'refresh'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'inspect'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QModelIndex, std::false_type>,
        // method 'onListBoxSelectionChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QItemSelection, std::false_type>,
        QtPrivate::TypeAndForceComplete<QItemSelection, std::false_type>,
        // method 'onFontChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::FindObjectsDialog::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<FindObjectsDialog *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->invalidate(); break;
        case 1: _t->refresh(); break;
        case 2: _t->inspect((*reinterpret_cast< std::add_pointer_t<QModelIndex>>(_a[1]))); break;
        case 3: _t->onListBoxSelectionChanged((*reinterpret_cast< std::add_pointer_t<QItemSelection>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<QItemSelection>>(_a[2]))); break;
        case 4: _t->onFontChanged(); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::FindObjectsDialog::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::FindObjectsDialog::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__FindObjectsDialog.stringdata0))
        return static_cast<void*>(this);
    return QDialog::qt_metacast(_clname);
}

int omnetpp::qtenv::FindObjectsDialog::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QDialog::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 5)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 5;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 5)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 5;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
