/****************************************************************************
** Meta object code from reading C++ file 'objecttreeinspector.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "objecttreeinspector.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'objecttreeinspector.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector_t {
    uint offsetsAndSizes[20];
    char stringdata0[36];
    char stringdata1[8];
    char stringdata2[1];
    char stringdata3[12];
    char stringdata4[6];
    char stringdata5[14];
    char stringdata6[18];
    char stringdata7[24];
    char stringdata8[18];
    char stringdata9[4];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector_t qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector = {
    {
        QT_MOC_LITERAL(0, 35),  // "omnetpp::qtenv::ObjectTreeIns..."
        QT_MOC_LITERAL(36, 7),  // "onClick"
        QT_MOC_LITERAL(44, 0),  // ""
        QT_MOC_LITERAL(45, 11),  // "QModelIndex"
        QT_MOC_LITERAL(57, 5),  // "index"
        QT_MOC_LITERAL(63, 13),  // "onDoubleClick"
        QT_MOC_LITERAL(77, 17),  // "gatherVisibleData"
        QT_MOC_LITERAL(95, 23),  // "gatherVisibleDataIfSafe"
        QT_MOC_LITERAL(119, 17),  // "createContextMenu"
        QT_MOC_LITERAL(137, 3)   // "pos"
    },
    "omnetpp::qtenv::ObjectTreeInspector",
    "onClick",
    "",
    "QModelIndex",
    "index",
    "onDoubleClick",
    "gatherVisibleData",
    "gatherVisibleDataIfSafe",
    "createContextMenu",
    "pos"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__ObjectTreeInspector[] = {

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
       1,    1,   44,    2, 0x08,    1 /* Private */,
       5,    1,   47,    2, 0x08,    3 /* Private */,
       6,    0,   50,    2, 0x08,    5 /* Private */,
       7,    0,   51,    2, 0x08,    6 /* Private */,
       8,    1,   52,    2, 0x0a,    7 /* Public */,

 // slots: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Bool,
    QMetaType::Bool,
    QMetaType::Void, QMetaType::QPoint,    9,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::ObjectTreeInspector::staticMetaObject = { {
    QMetaObject::SuperData::link<Inspector::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__ObjectTreeInspector,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<ObjectTreeInspector, std::true_type>,
        // method 'onClick'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QModelIndex, std::false_type>,
        // method 'onDoubleClick'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QModelIndex, std::false_type>,
        // method 'gatherVisibleData'
        QtPrivate::TypeAndForceComplete<bool, std::false_type>,
        // method 'gatherVisibleDataIfSafe'
        QtPrivate::TypeAndForceComplete<bool, std::false_type>,
        // method 'createContextMenu'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPoint, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::ObjectTreeInspector::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ObjectTreeInspector *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->onClick((*reinterpret_cast< std::add_pointer_t<QModelIndex>>(_a[1]))); break;
        case 1: _t->onDoubleClick((*reinterpret_cast< std::add_pointer_t<QModelIndex>>(_a[1]))); break;
        case 2: { bool _r = _t->gatherVisibleData();
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 3: { bool _r = _t->gatherVisibleDataIfSafe();
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 4: _t->createContextMenu((*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[1]))); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::ObjectTreeInspector::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::ObjectTreeInspector::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__ObjectTreeInspector.stringdata0))
        return static_cast<void*>(this);
    return Inspector::qt_metacast(_clname);
}

int omnetpp::qtenv::ObjectTreeInspector::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = Inspector::qt_metacall(_c, _id, _a);
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
