/****************************************************************************
** Meta object code from reading C++ file 'timelineinspector.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "timelineinspector.h"
#include <QtCore/qmetatype.h>
#include <QtCore/QList>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'timelineinspector.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector_t {
    uint offsetsAndSizes[24];
    char stringdata0[34];
    char stringdata1[21];
    char stringdata2[1];
    char stringdata3[14];
    char stringdata4[18];
    char stringdata5[16];
    char stringdata6[8];
    char stringdata7[10];
    char stringdata8[27];
    char stringdata9[9];
    char stringdata10[7];
    char stringdata11[14];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector_t qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector = {
    {
        QT_MOC_LITERAL(0, 33),  // "omnetpp::qtenv::TimeLineInspe..."
        QT_MOC_LITERAL(34, 20),  // "runPreferencesDialog"
        QT_MOC_LITERAL(55, 0),  // ""
        QT_MOC_LITERAL(56, 13),  // "onFontChanged"
        QT_MOC_LITERAL(70, 17),  // "createContextMenu"
        QT_MOC_LITERAL(88, 15),  // "QList<cObject*>"
        QT_MOC_LITERAL(104, 7),  // "objects"
        QT_MOC_LITERAL(112, 9),  // "globalPos"
        QT_MOC_LITERAL(122, 26),  // "setObjectToObjectInspector"
        QT_MOC_LITERAL(149, 8),  // "cObject*"
        QT_MOC_LITERAL(158, 6),  // "object"
        QT_MOC_LITERAL(165, 13)   // "openInspector"
    },
    "omnetpp::qtenv::TimeLineInspector",
    "runPreferencesDialog",
    "",
    "onFontChanged",
    "createContextMenu",
    "QList<cObject*>",
    "objects",
    "globalPos",
    "setObjectToObjectInspector",
    "cObject*",
    "object",
    "openInspector"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__TimeLineInspector[] = {

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
       1,    0,   44,    2, 0x08,    1 /* Private */,
       3,    0,   45,    2, 0x08,    2 /* Private */,
       4,    2,   46,    2, 0x0a,    3 /* Public */,
       8,    1,   51,    2, 0x0a,    6 /* Public */,
      11,    1,   54,    2, 0x0a,    8 /* Public */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 5, QMetaType::QPoint,    6,    7,
    QMetaType::Void, 0x80000000 | 9,   10,
    QMetaType::Void, 0x80000000 | 9,   10,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::TimeLineInspector::staticMetaObject = { {
    QMetaObject::SuperData::link<Inspector::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__TimeLineInspector,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<TimeLineInspector, std::true_type>,
        // method 'runPreferencesDialog'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onFontChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'createContextMenu'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QVector<cObject*>, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPoint, std::false_type>,
        // method 'setObjectToObjectInspector'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'openInspector'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::TimeLineInspector::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<TimeLineInspector *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->runPreferencesDialog(); break;
        case 1: _t->onFontChanged(); break;
        case 2: _t->createContextMenu((*reinterpret_cast< std::add_pointer_t<QList<cObject*>>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[2]))); break;
        case 3: _t->setObjectToObjectInspector((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        case 4: _t->openInspector((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::TimeLineInspector::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::TimeLineInspector::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__TimeLineInspector.stringdata0))
        return static_cast<void*>(this);
    return Inspector::qt_metacast(_clname);
}

int omnetpp::qtenv::TimeLineInspector::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
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
