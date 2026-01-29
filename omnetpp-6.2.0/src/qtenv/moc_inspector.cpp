/****************************************************************************
** Meta object code from reading C++ file 'inspector.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "inspector.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'inspector.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__Inspector_t {
    uint offsetsAndSizes[30];
    char stringdata0[26];
    char stringdata1[17];
    char stringdata2[1];
    char stringdata3[9];
    char stringdata4[7];
    char stringdata5[20];
    char stringdata6[23];
    char stringdata7[10];
    char stringdata8[10];
    char stringdata9[10];
    char stringdata10[7];
    char stringdata11[10];
    char stringdata12[14];
    char stringdata13[18];
    char stringdata14[9];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__Inspector_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__Inspector_t qt_meta_stringdata_omnetpp__qtenv__Inspector = {
    {
        QT_MOC_LITERAL(0, 25),  // "omnetpp::qtenv::Inspector"
        QT_MOC_LITERAL(26, 16),  // "selectionChanged"
        QT_MOC_LITERAL(43, 0),  // ""
        QT_MOC_LITERAL(44, 8),  // "cObject*"
        QT_MOC_LITERAL(53, 6),  // "object"
        QT_MOC_LITERAL(60, 19),  // "objectDoubleClicked"
        QT_MOC_LITERAL(80, 22),  // "inspectedObjectChanged"
        QT_MOC_LITERAL(103, 9),  // "newObject"
        QT_MOC_LITERAL(113, 9),  // "oldObject"
        QT_MOC_LITERAL(123, 9),  // "setObject"
        QT_MOC_LITERAL(133, 6),  // "goBack"
        QT_MOC_LITERAL(140, 9),  // "goForward"
        QT_MOC_LITERAL(150, 13),  // "inspectParent"
        QT_MOC_LITERAL(164, 17),  // "findObjectsWithin"
        QT_MOC_LITERAL(182, 8)   // "goUpInto"
    },
    "omnetpp::qtenv::Inspector",
    "selectionChanged",
    "",
    "cObject*",
    "object",
    "objectDoubleClicked",
    "inspectedObjectChanged",
    "newObject",
    "oldObject",
    "setObject",
    "goBack",
    "goForward",
    "inspectParent",
    "findObjectsWithin",
    "goUpInto"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__Inspector[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       9,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       3,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   68,    2, 0x06,    1 /* Public */,
       5,    1,   71,    2, 0x06,    3 /* Public */,
       6,    2,   74,    2, 0x06,    5 /* Public */,

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       9,    1,   79,    2, 0x0a,    8 /* Public */,
      10,    0,   82,    2, 0x0a,   10 /* Public */,
      11,    0,   83,    2, 0x0a,   11 /* Public */,
      12,    0,   84,    2, 0x0a,   12 /* Public */,
      13,    0,   85,    2, 0x0a,   13 /* Public */,
      14,    0,   86,    2, 0x09,   14 /* Protected */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3, 0x80000000 | 3,    7,    8,

 // slots: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::Inspector::staticMetaObject = { {
    QMetaObject::SuperData::link<QWidget::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__Inspector.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__Inspector,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__Inspector_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<Inspector, std::true_type>,
        // method 'selectionChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'objectDoubleClicked'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'inspectedObjectChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'setObject'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'goBack'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'goForward'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'inspectParent'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'findObjectsWithin'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'goUpInto'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::Inspector::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<Inspector *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->selectionChanged((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        case 1: _t->objectDoubleClicked((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        case 2: _t->inspectedObjectChanged((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[2]))); break;
        case 3: _t->setObject((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        case 4: _t->goBack(); break;
        case 5: _t->goForward(); break;
        case 6: _t->inspectParent(); break;
        case 7: _t->findObjectsWithin(); break;
        case 8: _t->goUpInto(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (Inspector::*)(cObject * );
            if (_t _q_method = &Inspector::selectionChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (Inspector::*)(cObject * );
            if (_t _q_method = &Inspector::objectDoubleClicked; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (Inspector::*)(cObject * , cObject * );
            if (_t _q_method = &Inspector::inspectedObjectChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 2;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::Inspector::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::Inspector::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__Inspector.stringdata0))
        return static_cast<void*>(this);
    return QWidget::qt_metacast(_clname);
}

int omnetpp::qtenv::Inspector::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QWidget::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 9)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 9;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 9)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 9;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::Inspector::selectionChanged(cObject * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::Inspector::objectDoubleClicked(cObject * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}

// SIGNAL 2
void omnetpp::qtenv::Inspector::inspectedObjectChanged(cObject * _t1, cObject * _t2)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))) };
    QMetaObject::activate(this, &staticMetaObject, 2, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
